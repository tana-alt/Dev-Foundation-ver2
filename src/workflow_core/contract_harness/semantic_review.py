from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.agent_tools import role_agent_tools
from workflow_core.contract_harness.command_runner import (
    command_result_artifact,
    env_timeout_s,
    run_command,
)
from workflow_core.contract_harness.config import ConfigError, control_root
from workflow_core.contract_harness.evidence import machine_artifact_hashes
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.metric_evidence import metric_evidence
from workflow_core.contract_harness.quality import (
    quality_result,
    tool_candidates_result,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.scope_map import scope_map_result
from workflow_core.contract_harness.snapshot import diff_index
from workflow_core.contract_harness.verifier import all_passed
from workflow_core.contract_harness.verify import recompute_machine_evidence
from workflow_core.contract_harness.worktree import (
    resolve_candidate_workspace,
    workspace_candidate_hash,
)

_INLINE_DIFF_MAX_BYTES = 64 * 1024


def run_command_profile(
    root: Path,
    task_id: str,
    reviewer_id: str,
    profile: dict[str, Any],
) -> tuple[str, list[str], str]:
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    if not _machine_ready(root, task_id, verify_result):
        return "block", ["machine_failed"], "machine verification failed before semantic review"
    try:
        workspace = resolve_candidate_workspace(
            root,
            task_id,
            expected_hash=str(verify_result.get("candidate_diff_sha256")),
        )
    except (OSError, ValueError) as exc:
        return "block", ["missing_repro"], str(exc)
    workspace_path = Path(str(workspace["path"]))
    before_hash = workspace_candidate_hash(workspace_path, task_id)
    packet_path, output_path = _write_packet(root, task_id, reviewer_id, verify_result, workspace)
    completed = run_command(
        _command(root, profile, packet_path, output_path, task_id),
        cwd=workspace_path,
        timeout_s=env_timeout_s("FOUNDATION_REVIEW_TIMEOUT_S", 900),
        env={
            **os.environ,
            "HARNESS_REVIEW_PACKET": str(packet_path),
            "HARNESS_REVIEW_OUTPUT": str(output_path),
            "HARNESS_REVIEW_WORKSPACE": str(workspace_path),
            "HARNESS_TASK_ID": task_id,
        },
    )
    activity = _agent_activity(root, task_id, reviewer_id)
    _write_command_result(root, task_id, reviewer_id, completed, activity=activity)
    if int(completed["exit_code"]) != 0:
        return "block", ["reviewer_infra_failed"], _infra_failure_reason(activity)
    after_hash = workspace_candidate_hash(workspace_path, task_id)
    if after_hash != before_hash:
        return "block", ["semantic_gap"], "reviewer mutated candidate workspace"
    return _read_ai_verdict(output_path, str(completed.get("stdout") or ""))


def _machine_ready(root: Path, task_id: str, verify_result: dict[str, Any]) -> bool:
    candidate = task_dir(root, task_id) / "candidate.diff"
    scope = _mapping(verify_result.get("scope"))
    hashes = machine_artifact_hashes(root, task_id)
    return (
        verify_result.get("status") == "pass"
        and file_hash(candidate) == verify_result.get("candidate_diff_sha256")
        and verify_result.get("machine_evidence_sha256")
        == recompute_machine_evidence(verify_result)
        and int(scope.get("violation_count", 0)) == 0
        and all(hashes.values())
        and verify_result.get("scope_map_reverse_sha256") == hashes["scope_map_reverse_sha256"]
        and all_passed(
            [item for item in verify_result.get("verifiers", []) if isinstance(item, dict)]
        )
    )


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _write_packet(
    root: Path,
    task_id: str,
    reviewer_id: str,
    verify_result: dict[str, Any],
    workspace: dict[str, Any],
) -> tuple[Path, Path]:
    reviews_dir = task_dir(root, task_id) / "reviews"
    packet_path = reviews_dir / f"{reviewer_id}.review-packet.json"
    output_path = reviews_dir / f"{reviewer_id}.review-output.json"
    write_json(packet_path, _packet(root, task_id, verify_result, workspace))
    return packet_path, output_path


def _packet(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
    workspace: dict[str, Any],
) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    mutation_result = _mutation_result(runtime)
    quality = quality_result(root, task_id)
    tool_candidates = tool_candidates_result(root, task_id)
    metrics = metric_evidence(root, task_id)
    reverse_scope_map = scope_map_result(root, task_id, "reverse")
    candidate_path = runtime / "candidate.diff"
    candidate_diff = candidate_path.read_text(encoding="utf-8")
    candidate_diff_inline, omitted_required, requires_artifact_read = _bounded_diff(candidate_diff)
    contract = read_json(runtime / "contract.lock.json")
    return {
        "task_id": task_id,
        "capsule": _context_payload(read_json(runtime / "capsule.json")),
        "contract": contract,
        "scope_contract": contract["scope_contract"],
        "agent_tools": role_agent_tools(root, task_id, "reviewer"),
        "writer_handoff": _writer_handoff(runtime),
        "review_workspace": workspace,
        "scope_map": {"reverse": reverse_scope_map},
        "candidate_diff": candidate_diff_inline,
        "candidate_diff_path": str(candidate_path),
        "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
        "candidate_diff_index": diff_index(candidate_diff),
        "diff_instruction": (
            "Review the candidate diff and machine evidence. If candidate_diff is empty, "
            "read candidate_diff_path and verify it against candidate_diff_sha256. "
            "Block when required diff or evidence is absent."
        ),
        "omitted_required_evidence": omitted_required,
        "requires_artifact_read": requires_artifact_read,
        "verify_result": verify_result,
        "mutation_result": mutation_result,
        "quality_result": quality,
        "tool_candidates": tool_candidates,
        "metric_evidence": metrics,
        "reviewer_policy": _reviewer_policy(),
        "test_interpretation": _test_interpretation(
            verify_result,
            mutation_result,
            quality,
            tool_candidates,
            metrics,
        ),
    }


def _bounded_diff(candidate_diff: str) -> tuple[str, list[str], bool]:
    if len(candidate_diff.encode("utf-8")) <= _INLINE_DIFF_MAX_BYTES:
        return candidate_diff, [], False
    return "", ["candidate_diff"], True


def _test_interpretation(
    verify_result: dict[str, Any],
    mutation_result: dict[str, Any],
    quality: dict[str, Any],
    tool_candidates: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    verifiers = [item for item in verify_result.get("verifiers", []) if isinstance(item, dict)]
    failed = [str(item.get("id")) for item in verifiers if item.get("status") != "pass"]
    passed = [str(item.get("id")) for item in verifiers if item.get("status") == "pass"]
    required_passed = verify_result.get("status") == "pass" and not failed
    return {
        "overall_status": "pass" if required_passed else "fail",
        "required_verifiers_passed": required_passed,
        "passed_verifiers": passed,
        "failed_verifiers": failed,
        "mutation": {
            "status": str(mutation_result.get("status", "not_configured")),
            "survivor_count": int(mutation_result.get("survivor_count", 0)),
            "survivors": list(mutation_result.get("survivors") or []),
        },
        "quality": {
            "status": str(quality.get("status", "pass")),
            "hard_failure_count": len(list(quality.get("hard_failures") or [])),
            "review_flag_count": len(list(quality.get("review_flags") or [])),
        },
        "tool_candidates": {
            "status": str(tool_candidates.get("status", "pass")),
            "candidate_count": len(list(tool_candidates.get("candidates") or [])),
        },
        "metrics": {
            "status": str(metrics.get("status", "absent")),
            "has_eval": bool(metrics.get("eval")),
            "nfr_count": len(list(metrics.get("nfr") or [])),
            "bench_count": len(list(metrics.get("bench") or [])),
        },
    }


def _mutation_result(runtime: Path) -> dict[str, Any]:
    path = runtime / "mutation-result.json"
    if path.is_file():
        return read_json(path)
    return {"status": "not_configured", "survivor_count": 0, "survivors": []}


def _writer_handoff(runtime: Path) -> dict[str, Any]:
    path = runtime / "submission.json"
    if not path.is_file():
        return {}
    data = read_json(path)
    handoff = data.get("writer_handoff")
    return _context_payload(handoff) if isinstance(handoff, dict) else {}


def _context_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    sanitized.pop("agent_skills", None)
    return sanitized


def _reviewer_policy() -> dict[str, str]:
    return {
        "quality": (
            "Treat quality metrics as routing evidence, not the goal. "
            "Hard machine failures cover objective artifact breakage; review flags need "
            "semantic judgement. Block threshold gaming or meaningless splitting when it "
            "harms clarity."
        ),
        "tool_reuse": (
            "Approve new tools only when they are reusable beyond the current task, "
            "parameterized, deterministic, and backed by durable checks. Block task-specific "
            "or check-gaming tools even when their mechanical probe passes."
        ),
        "stale_evidence": (
            "Evidence hashes define freshness. When one evidence artifact changes, rely only "
            "on reviewers that consumed fresh evidence and rerun the affected reviewer lane."
        ),
        "scope_map": (
            "The diff is the observed implementation scope. Use the reverse scope map as "
            "impact evidence, not as a hard constraint or proof that no other impact exists."
        ),
    }


def _command(
    root: Path,
    profile: dict[str, Any],
    packet_path: Path,
    output_path: Path,
    task_id: str,
) -> list[str]:
    command = profile.get("command")
    if not isinstance(command, list) or not command:
        raise ConfigError("semantic reviewer command must be a non-empty list")
    repo_root = control_root(root)
    replacements = {
        "{repo_root}": str(repo_root),
        "{review_packet}": str(packet_path),
        "{review_output}": str(output_path),
        "{task_id}": task_id,
        "{runtime_task_dir}": str(packet_path.parents[1]),
    }
    rendered = [_replace(str(part), replacements) for part in command]
    if "{review_packet}" not in " ".join(str(part) for part in command):
        rendered.extend([str(packet_path), str(output_path)])
    return rendered


def _replace(value: str, replacements: dict[str, str]) -> str:
    for token, replacement in replacements.items():
        value = value.replace(token, replacement)
    return value


def _read_ai_verdict(output_path: Path, stdout: str) -> tuple[str, list[str], str]:
    data = read_json(output_path) if output_path.is_file() else _json_from_stdout(stdout)
    verdict = str(data.get("verdict", ""))
    if verdict not in {"approve", "block"}:
        raise ConfigError("semantic reviewer verdict must be approve or block")
    labels = [str(item) for item in data.get("labels", []) if isinstance(item, str)]
    reason = str(data.get("reason", ""))
    return verdict, labels, reason


def _write_command_result(
    root: Path,
    task_id: str,
    reviewer_id: str,
    result: dict[str, Any],
    *,
    activity: dict[str, Any],
) -> None:
    write_json(
        task_dir(root, task_id) / "review-runs" / f"{reviewer_id}-command.json",
        {
            "task_id": task_id,
            "reviewer_id": reviewer_id,
            "mode": "command_profile",
            **command_result_artifact(result),
            "agent_activity": activity,
            "next_action": _next_action(activity),
            "resume_command": _resume_command(root, task_id, reviewer_id),
            "rerun_command": _rerun_command(root, task_id, reviewer_id),
            "written_by": "harness",
        },
    )


def _agent_activity(root: Path, task_id: str, reviewer_id: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    session_path = runtime / f"reviewer-session-{_safe_component(reviewer_id)}.json"
    if session_path.is_file():
        session = read_json(session_path)
        status = str(session.get("status") or "unknown")
        return {
            "status": "active" if status in {"ready", "active"} else "stopped",
            "source": str(session_path),
            "session_status": status,
            "reviewer_id": reviewer_id,
            "agent_id": str(session.get("agent_id") or ""),
        }
    for path in sorted((runtime / "comm" / "sessions").glob("*.json")):
        session = read_json(path)
        if session.get("role") != "reviewer":
            continue
        if str(session.get("agent_id") or "").split(".")[-1] != reviewer_id:
            continue
        status = str(session.get("status") or "unknown")
        return {
            "status": "active" if status in {"ready", "active"} else "stopped",
            "source": str(path),
            "session_status": status,
            "reviewer_id": reviewer_id,
            "agent_id": str(session.get("agent_id") or ""),
        }
    return {
        "status": "not_active",
        "source": "missing_reviewer_session",
        "reviewer_id": reviewer_id,
        "agent_id": "",
    }


def _infra_failure_reason(activity: dict[str, Any]) -> str:
    status = str(activity.get("status") or "unknown")
    if status == "active":
        return "semantic reviewer infrastructure failed; reviewer agent is active"
    return "semantic reviewer infrastructure failed; reviewer agent not active"


def _next_action(activity: dict[str, Any]) -> str:
    return (
        "rerun_semantic_review" if activity.get("status") == "active" else "resume_reviewer_agent"
    )


def _resume_command(root: Path, task_id: str, reviewer_id: str) -> str:
    harness = shlex.quote(str(_harness_path(root)))
    reviewer = shlex.quote(reviewer_id)
    return (
        f"HARNESS_ROLE=integrator {harness} spawn {task_id} --role reviewer "
        f"--reviewer-id {reviewer} --agent codex --comm"
    )


def _rerun_command(root: Path, task_id: str, reviewer_id: str) -> str:
    harness = shlex.quote(str(_harness_path(root)))
    reviewer = shlex.quote(reviewer_id)
    return f"HARNESS_ROLE=reviewer {harness} review {task_id} --run {reviewer}"


def _harness_path(root: Path) -> Path:
    candidate = root / "harness"
    if candidate.is_file():
        return candidate
    return Path(__file__).resolve().parents[3] / "harness"


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "agent"


def _json_from_stdout(stdout: str) -> dict[str, Any]:
    import json

    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ConfigError("semantic reviewer stdout must be a JSON object")
    return data
