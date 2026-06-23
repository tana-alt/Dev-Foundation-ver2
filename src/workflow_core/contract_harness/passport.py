from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import review_profile, review_settings
from workflow_core.contract_harness.evidence import reviewer_evidence_seen
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.status import task_status


def proof_passport(root: Path, task_id: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    status = task_status(root, task_id)
    contract = _read_optional(runtime / "contract.lock.json")
    verify = _read_optional(runtime / "verify-result.json")
    gate = _read_optional(runtime / "gate-result.json")
    integration = _read_optional(runtime / "integration-result.json")
    return {
        "schema_version": 1,
        "task_id": task_id,
        "task": _task_proof(contract),
        "candidate": _candidate_proof(runtime, verify, contract),
        "machine_proof": _machine_proof(verify),
        "review_proof": _review_proof(root, runtime, task_id, verify, gate),
        "policy_proof": _policy_proof(contract, gate, integration),
        "state_proof": status["state_store"],
        "artifacts": status["artifacts"],
        "phase": status["phase"],
        "next_action": status["next_action"],
        "written_by": "harness",
    }


def proof_passport_markdown(passport: dict[str, Any]) -> str:
    task = _mapping(passport.get("task"))
    candidate = _mapping(passport.get("candidate"))
    machine = _mapping(passport.get("machine_proof"))
    review = _mapping(passport.get("review_proof"))
    state = _mapping(passport.get("state_proof"))
    next_action = _mapping(passport.get("next_action"))
    command = next_action.get("command") or "none"
    return "\n".join(
        [
            f"# Proof Passport: {passport.get('task_id')}",
            "",
            f"- Goal: {task.get('goal_summary') or 'unknown'}",
            f"- Phase: {passport.get('phase')}",
            f"- Candidate: {candidate.get('diff_sha256') or 'missing'}",
            f"- Machine proof: {machine.get('status')} ({machine.get('evidence_sha256')})",
            f"- Review proof: {review.get('status')}",
            f"- State proof: {state.get('integrity')} ({state.get('current_event_sha256')})",
            f"- Next action: {next_action.get('status')} - {command}",
            "",
        ]
    )


def _task_proof(contract: dict[str, Any] | None) -> dict[str, Any]:
    if contract is None:
        return {"status": "missing"}
    goal = _mapping(contract.get("goal"))
    scope = _mapping(contract.get("scope_contract"))
    return {
        "status": "present",
        "goal_summary": goal.get("summary"),
        "scope": {
            "allowed_paths": list(scope.get("allowed_paths") or []),
            "forbidden_paths": list(scope.get("forbidden_paths") or []),
        },
    }


def _candidate_proof(
    runtime: Path,
    verify: dict[str, Any] | None,
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = runtime / "candidate.diff"
    candidate_hash = file_hash(candidate) if candidate.is_file() else None
    return {
        "candidate_id": None if verify is None else verify.get("candidate_id"),
        "diff_sha256": None if verify is None else verify.get("candidate_diff_sha256"),
        "actual_diff_sha256": candidate_hash,
        "base_sha": _first_present(
            verify,
            contract,
            key="base_sha",
            fallback_key="prepared_base_sha",
        ),
        "hash_matches": (
            None
            if verify is None or candidate_hash is None
            else candidate_hash == verify.get("candidate_diff_sha256")
        ),
    }


def _machine_proof(verify: dict[str, Any] | None) -> dict[str, Any]:
    if verify is None:
        return {"status": "missing", "verifiers": []}
    verifiers = [
        {
            "id": item.get("id"),
            "status": item.get("status"),
            "command": item.get("command"),
            "exit_code": item.get("exit_code"),
            "timed_out": item.get("timed_out"),
            "stdout_sha256": item.get("stdout_sha256"),
            "stderr_sha256": item.get("stderr_sha256"),
        }
        for item in verify.get("verifiers", [])
        if isinstance(item, dict)
    ]
    return {
        "status": verify.get("status"),
        "evidence_sha256": verify.get("machine_evidence_sha256"),
        "verifiers": verifiers,
        "scope_violation_count": _mapping(verify.get("scope")).get("violation_count", 0),
        "architecture_status": _mapping(verify.get("architecture_gate")).get("status"),
    }


def _review_proof(
    root: Path,
    runtime: Path,
    task_id: str,
    verify: dict[str, Any] | None,
    gate: dict[str, Any] | None,
) -> dict[str, Any]:
    settings = review_settings(root)
    expected = {str(item) for item in settings["reviewers"]}
    reviews_dir = runtime / "reviews"
    reviews = []
    if reviews_dir.is_dir():
        reviews = [
            review
            for path in sorted(reviews_dir.glob("*.json"))
            if (review := _read_optional(path)) is not None
        ]
    fresh = [item for item in reviews if _fresh_review(root, task_id, item, expected, verify)]
    fresh_approves = [item for item in fresh if item.get("verdict") == "approve"]
    fresh_blocks = [
        str(item.get("reviewer_id")) for item in fresh if item.get("verdict") == "block"
    ]
    status = "not_started"
    if fresh_blocks:
        status = "blocked"
    elif fresh_approves:
        status = "pass" if len(fresh_approves) >= int(settings["quorum"]) else "pending"
    gate_review = _mapping(gate.get("review")) if gate is not None else {}
    return {
        "status": status,
        "quorum": settings["quorum"],
        "fresh_approves": len(fresh_approves),
        "fresh_blocks": len(fresh_blocks),
        "fresh_reviewers": [str(item.get("reviewer_id")) for item in fresh],
        "blocking_verdicts": fresh_blocks,
        "gate_review": gate_review or None,
    }


def _policy_proof(
    contract: dict[str, Any] | None,
    gate: dict[str, Any] | None,
    integration: dict[str, Any] | None,
) -> dict[str, Any]:
    scope = _mapping(None if contract is None else contract.get("scope_contract"))
    return {
        "allowed_path_count": len(list(scope.get("allowed_paths") or [])),
        "forbidden_path_count": len(list(scope.get("forbidden_paths") or [])),
        "human_gate": "required_if_policy_or_protected_action",
        "gate_mergeable": None if gate is None else gate.get("mergeable"),
        "integration_status": None if integration is None else integration.get("status"),
    }


def _fresh_review(
    root: Path,
    task_id: str,
    review: dict[str, Any],
    expected: set[str],
    verify: dict[str, Any] | None,
) -> bool:
    if review.get("written_by") != "harness" or review.get("reviewer_id") not in expected:
        return False
    if verify is None:
        return False
    evidence = _mapping(review.get("evidence_seen"))
    reviewer_id = str(review.get("reviewer_id"))
    expected_evidence = reviewer_evidence_seen(
        root,
        task_id,
        verify,
        semantic=_uses_semantic_evidence(root, reviewer_id),
    )
    return all(evidence.get(key) == value for key, value in expected_evidence.items())


def _uses_semantic_evidence(root: Path, reviewer_id: str) -> bool:
    profile = review_profile(root, reviewer_id)
    return isinstance(profile, dict) and profile.get("kind") == "command"


def _read_optional(path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def _first_present(
    primary: dict[str, Any] | None,
    secondary: dict[str, Any] | None,
    *,
    key: str,
    fallback_key: str,
) -> Any:
    if primary is not None and primary.get(key) is not None:
        return primary.get(key)
    if secondary is not None:
        return secondary.get(fallback_key)
    return None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
