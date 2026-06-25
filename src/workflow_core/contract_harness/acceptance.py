from __future__ import annotations

import shlex
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import (
    ConfigError,
    control_root,
    harness_dir,
    load_yaml,
    task_config_dir,
)
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir


def load_task_policy(root: Path, task: dict[str, Any]) -> dict[str, Any] | None:
    policy_id = str(task.get("policy") or "").strip()
    task_id = str(task.get("id") or "")
    project_dir = task_config_dir(root, task_id) if task_id else harness_dir(root)
    has_project_policy = (
        project_dir != harness_dir(root) and (project_dir / "policy.yaml").is_file()
    )
    if not policy_id and has_project_policy:
        policy_id = project_dir.name
        path = project_dir / "policy.yaml"
    elif policy_id:
        project_policy = project_dir / "policies" / f"{_safe_policy_id(policy_id)}.yaml"
        path = (
            project_policy
            if project_dir != harness_dir(root) and project_policy.is_file()
            else harness_dir(root) / "policies" / f"{_safe_policy_id(policy_id)}.yaml"
        )
    else:
        return None
    policy = load_yaml(path)
    declared = policy.get("id")
    if declared is not None and str(declared) != policy_id:
        raise ConfigError(f"policy id mismatch: {policy_id}")
    return {
        "id": policy_id,
        "path": str(path.relative_to(control_root(root))),
        "goal": policy.get("goal"),
        "invariants": _list_of_maps(policy.get("invariants")),
        "acceptance_requirements": [
            str(item) for item in policy.get("acceptance_requirements") or []
        ],
        "verifiers": policy.get("verifiers") if isinstance(policy.get("verifiers"), dict) else {},
        "human_gates": [str(item) for item in policy.get("human_gates") or []],
        "metrics": [str(item) for item in policy.get("metrics") or []],
    }


def build_acceptance(
    root: Path,
    task_id: str,
    task: dict[str, Any],
    policy: dict[str, Any] | None,
    verifiers: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    acceptance = task.get("acceptance")
    if not isinstance(acceptance, dict):
        raise ConfigError("acceptance must be a mapping")
    mode = str(acceptance.get("mode") or "")
    if mode == "generated":
        return _legacy_acceptance(), None
    if mode != "agent_generated":
        raise ConfigError("acceptance.mode must be generated or agent_generated")
    proposal = {
        "schema_version": 1,
        "task_id": task_id,
        "mode": "agent_generated",
        "scope": str(task.get("scope") or ""),
        "criteria": _list_of_maps(acceptance.get("criteria")),
        "written_by": "harness",
    }
    if "human_gates" in acceptance:
        proposal["human_gates"] = [str(item) for item in acceptance.get("human_gates") or []]
    audit = audit_acceptance(root, proposal, policy, verifiers)
    return {
        "mode": "agent_generated",
        "criteria": proposal["criteria"],
        "audit": audit,
    }, proposal


def audit_acceptance(
    root: Path,
    proposal: dict[str, Any],
    policy: dict[str, Any] | None,
    verifiers: list[dict[str, Any]],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    criteria = _list_of_maps(proposal.get("criteria"))
    if not criteria:
        findings.append(_finding("missing_criteria", "acceptance criteria are required"))
    requirements = set(str(item) for item in (policy or {}).get("acceptance_requirements", []))
    verifier_commands = {str(item.get("command")) for item in verifiers if item.get("command")}
    if "every_criterion_has_proof" in requirements:
        for criterion in criteria:
            findings.extend(_proof_findings(root, criterion, verifier_commands))
    if "policy_invariants_are_mapped" in requirements:
        invariant_ids = {
            str(item.get("id"))
            for item in _list_of_maps((policy or {}).get("invariants"))
            if item.get("id")
        }
        mapped = {
            str(ref)
            for criterion in criteria
            for ref in criterion.get("policy_refs", [])
            if isinstance(ref, str)
        }
        missing = sorted(invariant_ids - mapped)
        for invariant_id in missing:
            findings.append(
                _finding("unmapped_policy", f"policy invariant is not mapped: {invariant_id}")
            )
    required_verifiers = [
        str(item) for item in ((policy or {}).get("verifiers", {}) or {}).get("required", [])
    ]
    if required_verifiers:
        verifier_ids = {str(item.get("id")) for item in verifiers}
        missing = sorted(set(required_verifiers) - verifier_ids)
        for verifier_id in missing:
            findings.append(
                _finding("missing_verifier", f"required verifier is not configured: {verifier_id}")
            )
    if "human_gates_are_explicit" in requirements and "human_gates" not in proposal:
        findings.append(_finding("missing_human_gates", "acceptance.human_gates is required"))
    if "scope_is_bounded" in requirements and not str(proposal.get("scope") or "").strip():
        findings.append(_finding("unknown_scope", "task scope is required"))
    return {
        "status": "pass" if not findings else "fail",
        "findings": findings,
        "written_by": "harness",
    }


def write_acceptance_rework(
    root: Path,
    task_id: str,
    *,
    audit: dict[str, Any],
    task: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    acceptance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "rework_required",
        "reason": "acceptance_audit_failed",
        "audit": audit,
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "rework-request.json", result)
    bottlenecks = append_bottleneck_event(
        root,
        task_id,
        phase="acceptance.audit",
        status="rework_required",
        reason="acceptance_audit_failed",
        required_input="agent acceptance proposal with policy coverage and proof commands",
        suggested_rework="map policy invariants and add proof.command for each criterion",
    )
    _write_rework_resume_capsule(
        root,
        task_id,
        audit=audit,
        bottleneck=bottlenecks["events"][-1] if bottlenecks.get("events") else None,
        task=task or {},
        policy=policy,
        acceptance=acceptance,
    )
    return result


def append_bottleneck_event(
    root: Path,
    task_id: str,
    *,
    phase: str,
    status: str,
    reason: str,
    required_input: str = "",
    suggested_rework: str = "",
) -> dict[str, Any]:
    path = task_dir(root, task_id) / "bottleneck-events.json"
    try:
        data = read_json(path)
    except (OSError, ValueError):
        data = {
            "schema_version": 1,
            "task_id": task_id,
            "events": [],
            "written_by": "harness",
        }
    events = data.setdefault("events", [])
    if not isinstance(events, list):
        events = []
        data["events"] = events
    events.append(
        {
            "phase": phase,
            "status": status,
            "reason": reason,
            "first_seen_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "elapsed_ms": 0,
            "required_input": required_input,
            "suggested_rework": suggested_rework,
        }
    )
    write_json(path, data)
    return data


def _legacy_acceptance() -> dict[str, Any]:
    return {
        "mode": "generated",
        "all_required_verifiers_pass": True,
        "scope_violation_count": 0,
        "proposals_affect_acceptance": False,
    }


def _finding(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _proof_findings(
    root: Path,
    criterion: dict[str, Any],
    verifier_commands: set[str],
) -> list[dict[str, str]]:
    proof = criterion.get("proof")
    criterion_id = str(criterion.get("id") or "<unknown>")
    if not isinstance(proof, dict):
        return [_finding("missing_proof", f"{criterion_id} requires proof")]
    kind = str(proof.get("kind") or "")
    if kind not in {"test", "command", "artifact_check"}:
        return [_finding("invalid_proof", f"{criterion_id} proof.kind is not supported")]
    if kind in {"test", "command"}:
        command = proof.get("command")
        if not isinstance(command, str) or not command.strip():
            return [_finding("missing_proof", f"{criterion_id} requires proof.command")]
        if not _command_is_executable(root, command, verifier_commands):
            return [
                _finding("invalid_proof_command", f"{criterion_id} proof.command is not runnable")
            ]
        return []
    artifact = proof.get("path") or proof.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        return [_finding("missing_artifact_check", f"{criterion_id} requires proof.path")]
    return []


def _command_is_executable(root: Path, command: str, verifier_commands: set[str]) -> bool:
    if command in verifier_commands:
        return True
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    program = parts[0]
    if shutil.which(program):
        return True
    candidate = Path(program)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.is_file()


def _list_of_maps(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_policy_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "policy"


def _write_rework_resume_capsule(
    root: Path,
    task_id: str,
    *,
    audit: dict[str, Any],
    bottleneck: dict[str, Any] | None,
    task: dict[str, Any],
    policy: dict[str, Any] | None,
    acceptance: dict[str, Any] | None,
) -> None:
    write_json(
        task_dir(root, task_id) / "resume-capsule.json",
        {
            "schema_version": 1,
            "task_id": task_id,
            "role": "writer",
            "task_goal": task.get("goal") or task.get("intent", {}).get("summary"),
            "policy": policy,
            "locked_acceptance": None,
            "proposed_acceptance": acceptance,
            "current_phase": "rework_required",
            "latest_evidence": [{"type": "bottleneck_event", "value": bottleneck}]
            if bottleneck
            else [],
            "unresolved": {
                "status": "rework_required",
                "reason": "acceptance_audit_failed",
                "audit": audit,
            },
            "next_expected_action": "revise acceptance proposal and run prepare again",
            "written_by": "harness",
        },
    )
