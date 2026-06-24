from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.gate import gate_task
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.review import collect
from workflow_core.contract_harness.runtime_paths import task_dir

_WRITER_REWORK_REASONS = {
    "architecture_gate_block",
    "machine_gate_failed",
    "oracle_requirement_unmet",
    "review_blocked",
    "unexpected_actions",
}

_INTEGRATOR_REASONS = {
    "architecture_gate_mismatch",
    "candidate_hash_mismatch",
    "contract_semantic_mismatch",
    "evidence_hash_mismatch",
    "review_quorum_unmet",
    "reviewer_head_changed",
    "semantic_review_required",
}


def run_post_review_gate(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    """Run the deterministic hook after review pass and before PR creation."""
    try:
        review = collect(root, task_id)
    except (OSError, ValueError, KeyError) as exc:
        return _write_result(
            root,
            task_id,
            status="blocked",
            classification="harness_error",
            reason="invalid_runtime_state",
            review={},
            gate={},
            error=str(exc),
        ), 1
    if review.get("review_pass") is not True:
        reason = _review_reason(review)
        classification = _classify_reason(reason)
        return _write_result(
            root,
            task_id,
            status="blocked",
            classification=classification,
            reason=reason,
            review=review,
            gate={},
        ), 1
    try:
        gate, code = gate_task(root, task_id, auto_review=False)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        return _write_result(
            root,
            task_id,
            status="blocked",
            classification="harness_error",
            reason="invalid_runtime_state",
            review=review,
            gate={},
            error=str(exc),
        ), 1
    reason = str(gate.get("reason") or "ok")
    if code == 0 and gate.get("mergeable") is True and reason == "ok":
        classification = "mechanical_gate_passed"
        status = "passed"
    else:
        classification = _classify_reason(reason)
        status = "blocked"
    return _write_result(
        root,
        task_id,
        status=status,
        classification=classification,
        reason=reason,
        review=_mapping(gate.get("review")) or review,
        gate=gate,
    ), 0 if status == "passed" else 1


def ensure_post_review_gate_passed(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    return run_post_review_gate(root, task_id)


def post_review_gate_passed_for_candidate(root: Path, task_id: str, candidate_sha: str) -> bool:
    try:
        result = read_json(task_dir(root, task_id) / "post-review-gate-result.json")
    except (OSError, ValueError):
        return False
    return (
        result.get("status") == "passed"
        and result.get("classification") == "mechanical_gate_passed"
        and result.get("candidate_diff_sha256") == candidate_sha
    )


def _write_result(
    root: Path,
    task_id: str,
    *,
    status: str,
    classification: str,
    reason: str,
    review: dict[str, Any],
    gate: dict[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    candidate_sha = _candidate_sha(root, task_id, gate)
    result: dict[str, Any] = {
        "schema_version": 1,
        "task_id": task_id,
        "status": status,
        "classification": classification,
        "reason": reason,
        "candidate_id": candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
        "candidate_diff_sha256": candidate_sha or None,
        "machine_evidence_sha256": gate.get("machine_evidence_sha256")
        or _verify_field(root, task_id, "machine_evidence_sha256"),
        "review": review,
        "gate": gate,
        "next_action": _next_action(task_id, classification),
        "invariant_axis": "expected_input_happy_path"
        if classification == "mechanical_gate_passed"
        else "blocked_before_external_write",
        "written_by": "harness",
        "written_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if classification != "mechanical_gate_passed":
        result["adversarial_axis"] = "error_input_resilience"
    if error:
        result["error"] = error
    path = task_dir(root, task_id) / "post-review-gate-result.json"
    write_json(path, result)
    record_error = _record_post_review_gate(root, task_id, result)
    if status == "passed" and record_error:
        result["status"] = "blocked"
        result["classification"] = "harness_error"
        result["reason"] = "authority_record_failed"
        result["next_action"] = _next_action(task_id, "harness_error")
        result["invariant_axis"] = "blocked_before_external_write"
        result["adversarial_axis"] = "error_input_resilience"
        result["error"] = record_error
        write_json(path, result)
    return result


def _record_post_review_gate(root: Path, task_id: str, result: dict[str, Any]) -> str | None:
    candidate_sha = str(result.get("candidate_diff_sha256") or "")
    try:
        record_authority_artifact(
            root,
            task_id,
            "post-review-gate-result.json",
            event_type="POST_REVIEW_GATE",
            to_phase=WorkflowPhase.GATED
            if result.get("status") == "passed"
            else WorkflowPhase.BLOCKED,
            payload={
                "candidate_diff_sha256": result.get("candidate_diff_sha256"),
                "machine_evidence_sha256": result.get("machine_evidence_sha256"),
                "status": result.get("status"),
                "classification": result.get("classification"),
                "reason": result.get("reason"),
            },
            candidate_id=candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        return str(exc) or "record_authority_artifact_failed"
    return None


def _review_reason(review: dict[str, Any]) -> str:
    if review.get("fresh_blocks"):
        return "review_blocked"
    if review.get("blocking_verdicts"):
        return "review_blocked"
    if review.get("semantic_review_required") and not review.get("fresh_semantic_approves"):
        return "semantic_review_required"
    return "review_quorum_unmet"


def _classify_reason(reason: str) -> str:
    if reason == "ok":
        return "mechanical_gate_passed"
    if reason in _WRITER_REWORK_REASONS:
        return "writer_rework_required"
    if reason in _INTEGRATOR_REASONS or reason.startswith("reviewer_failed:"):
        return "integrator_required"
    return "harness_error"


def _next_action(task_id: str, classification: str) -> dict[str, str | None]:
    if classification == "mechanical_gate_passed":
        return {
            "status": "continue",
            "command": f"HARNESS_ROLE=integrator ./harness pr create {task_id}",
            "reason": "post-review mechanical gate passed",
        }
    if classification == "writer_rework_required":
        return {
            "status": "rework",
            "command": f"HARNESS_ROLE=writer ./harness status {task_id}",
            "reason": "candidate behavior or review evidence requires writer rework",
        }
    if classification == "integrator_required":
        return {
            "status": "fallback",
            "command": f"HARNESS_ROLE=integrator ./harness status {task_id}",
            "reason": "integrator fallback required for candidate/hash/review state mismatch",
        }
    return {
        "status": "blocked",
        "command": None,
        "reason": "Harness runtime state or command execution needs repair",
    }


def _candidate_sha(root: Path, task_id: str, gate: dict[str, Any]) -> str:
    value = gate.get("candidate_diff_sha256")
    if isinstance(value, str) and value:
        return value
    return _verify_field(root, task_id, "candidate_diff_sha256")


def _verify_field(root: Path, task_id: str, key: str) -> str:
    try:
        value = read_json(task_dir(root, task_id) / "verify-result.json").get(key)
    except (OSError, ValueError, KeyError):
        return ""
    return str(value or "")


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
