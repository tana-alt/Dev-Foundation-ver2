from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from workflow_core.completion import CheckOutcome, run_completion_gate, write_evidence
from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.architecture_gate import (
    canonical_architecture_gate,
    evaluate_architecture_gate,
)
from workflow_core.contract_harness.command_runner import env_timeout_s, run_command
from workflow_core.contract_harness.config import control_root, review_settings
from workflow_core.contract_harness.contract import (
    load_contract,
    load_verifier_plan,
    semantic_reproducible,
)
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.evidence import machine_artifact_hashes
from workflow_core.contract_harness.gitutil import head_sha
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.oracle_requirements import oracle_requirements_satisfied
from workflow_core.contract_harness.review import collect
from workflow_core.contract_harness.review_runner import (
    ReviewRunnerError,
    run_missing_reviewers,
    run_reviewer_in_process,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.snapshot import changed_repo_paths, snapshot_diff
from workflow_core.contract_harness.verifier import all_passed, run_verifiers
from workflow_core.contract_harness.worktree import resolve_candidate_workspace
from workflow_core.metrics_store import MetricsStore


def gate_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    base = _base_result(root, task_id)
    workspace = Path(str(base.get("candidate_workspace", {}).get("path", root)))
    if base["reason"] != "ok":
        base = _with_existing_blocking_review(root, task_id, base)
    if base["reason"] == "ok":
        base = _with_completion(root, task_id, base, workspace)
    if base["reason"] == "ok":
        before_review = head_sha(workspace)
        try:
            _auto_review(root, task_id)
        except ReviewRunnerError as exc:
            base["review"] = {
                "failed_reviewer": exc.reviewer_id,
                "run_result": exc.result,
            }
            base["reason"] = f"reviewer_failed:{exc.reviewer_id}"
            base["metrics"] = _metrics(root, task_id)
            base = _apply_metrics_policy(root, base)
            base["mergeable"] = False
            write_json(task_dir(root, task_id) / "gate-result.json", base)
            _record_gate(root, task_id, base)
            return base, 1
        after_review = head_sha(workspace)
        if before_review != after_review:
            base["reason"] = "reviewer_head_changed"
        else:
            base["review"] = collect(root, task_id)
            base["reason"] = _review_reason(base["review"])
    base["metrics"] = _metrics(root, task_id)
    base = _apply_metrics_policy(root, base)
    base["mergeable"] = base["reason"] == "ok"
    write_json(task_dir(root, task_id) / "gate-result.json", base)
    _record_gate(root, task_id, base)
    return base, 0 if base["mergeable"] else 1


def _with_existing_blocking_review(
    root: Path,
    task_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    try:
        summary = collect(root, task_id)
    except (OSError, ValueError, KeyError):
        return result
    if _review_reason(summary) == "review_blocked":
        result["review"] = summary
        result["reason"] = "review_blocked"
    return result


def _base_result(root: Path, task_id: str) -> dict[str, Any]:
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    candidate = task_dir(root, task_id) / "candidate.diff"
    lock = load_contract(root, task_id)
    candidate_sha = file_hash(candidate)
    workspace, workspace_reason = _candidate_workspace(root, task_id, verify_result)
    reason = workspace_reason or _preflight_reason(
        Path(str(workspace["path"])), task_id, verify_result, lock, candidate_sha
    )
    return {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id_from_patch_sha256(
            str(verify_result.get("candidate_diff_sha256") or "")
        ),
        "mergeable": False,
        "reason": reason,
        "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
        "candidate_workspace": workspace,
        "review": {},
        "completion": {"status": "not_run"},
    }


def _record_gate(root: Path, task_id: str, result: dict[str, Any]) -> None:
    candidate_sha = str(result.get("candidate_diff_sha256") or "")
    record_authority_artifact(
        root,
        task_id,
        "gate-result.json",
        event_type="GATE",
        to_phase=WorkflowPhase.GATED if result.get("mergeable") is True else WorkflowPhase.BLOCKED,
        payload={
            "candidate_diff_sha256": candidate_sha,
            "machine_evidence_sha256": result.get("machine_evidence_sha256"),
            "mergeable": result.get("mergeable"),
            "reason": result.get("reason"),
        },
        candidate_id=candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
    )


def _candidate_workspace(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    try:
        return (
            resolve_candidate_workspace(
                root,
                task_id,
                expected_hash=str(verify_result.get("candidate_diff_sha256")),
            ),
            None,
        )
    except (OSError, ValueError) as exc:
        return {"path": str(root), "status": "unavailable", "reason": str(exc)}, str(exc)


def _preflight_reason(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
    lock: dict[str, Any],
    candidate_sha: str,
) -> str:
    if candidate_sha != verify_result.get("candidate_diff_sha256"):
        return "candidate_hash_mismatch"
    if not semantic_reproducible(root, task_id, lock):
        return "contract_semantic_mismatch"
    if verify_result.get("status") != "pass":
        return "machine_gate_failed"
    if not _architecture_gate_matches_current_diff(root, task_id, verify_result, lock):
        return "architecture_gate_mismatch"
    architecture_gate = canonical_architecture_gate(verify_result.get("architecture_gate"))
    if architecture_gate.get("status") == "block":
        return "architecture_gate_block"
    requirements_ok, _unmet = oracle_requirements_satisfied(root, task_id, verify_result)
    if not requirements_ok:
        return "oracle_requirement_unmet"
    if not _matches_machine_artifact_hashes(root, task_id, verify_result):
        return "evidence_hash_mismatch"
    if _current_diff_hash(root, lock) != verify_result.get("candidate_diff_sha256"):
        return "candidate_hash_mismatch"
    return "ok"


def _architecture_gate_matches_current_diff(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
    lock: dict[str, Any],
) -> bool:
    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)
    recomputed = evaluate_architecture_gate(
        root,
        base_sha=str(lock["prepared_base_sha"]),
        diff_text=diff_text,
        changed_paths=paths,
    )
    return canonical_architecture_gate(recomputed) == canonical_architecture_gate(
        verify_result.get("architecture_gate")
    )


def _matches_machine_artifact_hashes(
    root: Path,
    task_id: str,
    verify_result: dict[str, Any],
) -> bool:
    return all(
        verify_result.get(key) == value
        for key, value in machine_artifact_hashes(root, task_id).items()
    )


def _with_completion(
    root: Path,
    task_id: str,
    result: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    before = head_sha(workspace)
    completed = _run_completion_check(workspace, task_id)
    after = head_sha(workspace)
    diff_text = (task_dir(root, task_id) / "candidate.diff").read_text(encoding="utf-8")
    verdict, evidence = run_completion_gate(
        diff_text,
        str(result["candidate_diff_sha256"]),
        CheckOutcome(command=str(completed["command"]), exit_code=int(str(completed["exit_code"]))),
        datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    evidence_path = write_evidence(
        evidence,
        artifact_dir=_completion_artifact_dir(root, task_id),
    )
    result["completion"] = {
        "status": "pass" if verdict.passed else "fail",
        "evidence_path": str(evidence_path),
        "command": str(completed["command"]),
    }
    if "verifiers" in completed:
        result["completion"]["verifiers"] = completed["verifiers"]
    if not verdict.passed or before != after:
        result["reason"] = "machine_gate_failed"
    return result


def _completion_artifact_dir(root: Path, task_id: str) -> Path:
    if (root / ".harness-worktree.json").is_file():
        return task_dir(root, task_id) / "completion-evidence"
    return root / "artifact" / task_id / "evidence"


def _run_make(root: Path) -> dict[str, object]:
    tier = os.environ.get("FOUNDATION_GATE_TIER", "check-required")
    completed = run_command(
        ["make", tier],
        cwd=root,
        timeout_s=env_timeout_s("FOUNDATION_GATE_TIMEOUT_S", 900),
    )
    return {
        "command": f"make {tier}",
        "exit_code": int(completed["exit_code"]),
        "duration_ms": completed["duration_ms"],
        "timed_out": completed["timed_out"],
    }


def _run_completion_check(root: Path, task_id: str) -> dict[str, object]:
    if "FOUNDATION_GATE_TIER" in os.environ:
        return _run_make(root)
    verifiers = run_verifiers(root, load_verifier_plan(root, task_id))
    return {
        "command": "harness verifiers: " + ", ".join(str(item.get("id", "")) for item in verifiers),
        "exit_code": 0 if all_passed(verifiers) else 1,
        "verifiers": verifiers,
    }


def _auto_review(root: Path, task_id: str) -> None:
    run_missing_reviewers(
        root,
        task_id,
        lambda reviewer_id: run_reviewer_in_process(root, task_id, reviewer_id),
    )


def _review_reason(summary: dict[str, Any]) -> str:
    if summary.get("review_pass") is True:
        return "ok"
    if summary.get("fresh_blocks"):
        return "review_blocked"
    if summary.get("semantic_review_required") and not summary.get("fresh_semantic_approves"):
        return "semantic_review_required"
    return "review_quorum_unmet"


def _apply_metrics_policy(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    settings = review_settings(root)
    unexpected = result["metrics"].get("unexpected_actions") or []
    if result["reason"] == "ok" and settings["reject_unexpected_actions"] and unexpected:
        result["reason"] = "unexpected_actions"
    return result


def _current_diff_hash(root: Path, lock: dict[str, Any]) -> str:
    paths = changed_repo_paths(root, task_id=str(lock["task_id"]))
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)
    return file_hash_from_text(diff_text)


def file_hash_from_text(text: str) -> str:
    from workflow_core.contract_harness.hashing import sha256_text

    return sha256_text(text)


def _metrics(root: Path, task_id: str) -> dict[str, Any]:
    db = control_root(root) / "artifact" / task_id / "metrics" / "eval.db"
    packet_exposure = _packet_exposure(root, task_id)
    if not db.exists():
        metrics = _empty_metrics()
        metrics["packet_exposure"] = packet_exposure
        return metrics
    with MetricsStore(db) as store:
        rows = store.metrics()
        report = store.aggregate_stored()
    return {
        "usage_observed": bool(rows),
        "tool_calls": sum(int(str(row["tool_calls"])) for row in rows),
        "tool_call_rate": report.mean_tool_call_rate,
        "skill_uses": sum(int(str(row["skill_uses"])) for row in rows),
        "skill_usage_rate": report.mean_skill_usage_rate,
        "packet_exposure": packet_exposure,
        "unexpected_actions": sorted(
            {item for row in rows for item in cast(list[str], row["unexpected_actions"])}
        ),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "usage_observed": False,
        "tool_calls": 0,
        "tool_call_rate": 0.0,
        "skill_uses": 0,
        "skill_usage_rate": 0.0,
        "unexpected_actions": [],
    }


def _packet_exposure(root: Path, task_id: str) -> dict[str, Any]:
    out_dir = task_dir(root, task_id)
    try:
        tools = read_json(out_dir / "agent-tools.json")
        skills = read_json(out_dir / "agent-skills.json")
    except (OSError, ValueError):
        return {"status": "absent", "roles": {}}
    roles: dict[str, dict[str, Any]] = {}
    for role in ("writer", "reviewer", "integrator"):
        role_tools = [item for item in tools.get(role, []) if isinstance(item, dict)]
        role_skills = [item for item in skills.get(role, []) if isinstance(item, dict)]
        roles[role] = {
            "tool_count": len(role_tools),
            "skill_count": len(role_skills),
            "tools": [str(item.get("name", "")) for item in role_tools],
            "skills": [str(item.get("name", "")) for item in role_skills],
        }
    return {"status": "present", "roles": roles}
