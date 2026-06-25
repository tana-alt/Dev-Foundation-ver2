from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import head_sha
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.post_review_gate import run_post_review_gate
from workflow_core.contract_harness.review_runner import (
    ReviewRunnerError,
    run_missing_reviewers,
    run_reviewer_subprocess,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.submission import validate_submission


def dispatch_task(
    root: Path,
    task_id: str,
    *,
    harness_bin: Path,
) -> tuple[dict[str, Any], int]:
    try:
        validate_submission(root, task_id)
    except (OSError, ValueError, KeyError) as exc:
        reason = "stale_submission" if str(exc) == "stale_submission" else str(exc)
        result = _result(task_id, status="rework_required", reason=reason)
        write_json(task_dir(root, task_id) / "integration-result.json", result)
        return result, 1
    return integrate_task(root, task_id, harness_bin=harness_bin)


def integrate_task(
    root: Path,
    task_id: str,
    *,
    harness_bin: Path,
) -> tuple[dict[str, Any], int]:
    before = head_sha(root)
    try:
        _run_missing_reviewers(root, task_id, harness_bin)
    except ReviewRunnerError as exc:
        result = _result(
            task_id,
            status="rework_required",
            reason=f"reviewer_failed:{exc.reviewer_id}",
            head_unchanged=before == head_sha(root),
        )
        result["review"] = {
            "failed_reviewer": exc.reviewer_id,
            "run_result": exc.result,
        }
        write_json(task_dir(root, task_id) / "integration-result.json", result)
        return result, 1
    post_gate_result, gate_code = run_post_review_gate(root, task_id)
    after = head_sha(root)
    status = "integrated" if gate_code == 0 else "rework_required"
    result = _from_post_review_gate(task_id, status, post_gate_result, before == after, root)
    write_json(task_dir(root, task_id) / "integration-result.json", result)
    return result, 0 if status == "integrated" else 1


def _run_missing_reviewers(root: Path, task_id: str, harness_bin: Path) -> None:
    run_missing_reviewers(
        root,
        task_id,
        lambda reviewer_id: run_reviewer_subprocess(root, task_id, reviewer_id, harness_bin),
    )


def _from_gate(
    task_id: str,
    status: str,
    gate_result: dict[str, Any],
    head_unchanged: bool,
    root: Path,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "role": "integrator",
        "status": status,
        "reason": gate_result.get("reason", "ok"),
        "candidate_diff_sha256": gate_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": gate_result.get("machine_evidence_sha256"),
        "review": gate_result.get("review", {}),
        "completion": gate_result.get("completion", {}),
        "metrics": gate_result.get("metrics", {}),
        "head_unchanged": head_unchanged,
        "integration_workspace": {
            "path": str(root),
            "head_unchanged": head_unchanged,
        },
    }


def _from_post_review_gate(
    task_id: str,
    status: str,
    post_gate_result: dict[str, Any],
    head_unchanged: bool,
    root: Path,
) -> dict[str, Any]:
    gate_result = post_gate_result.get("gate")
    if not isinstance(gate_result, dict) or not gate_result:
        gate_result = post_gate_result
    result = _from_gate(task_id, status, gate_result, head_unchanged, root)
    result["post_review_gate"] = {
        "status": post_gate_result.get("status"),
        "classification": post_gate_result.get("classification"),
        "reason": post_gate_result.get("reason"),
        "next_action": post_gate_result.get("next_action"),
    }
    return result


def _result(
    task_id: str,
    *,
    status: str,
    reason: str,
    head_unchanged: bool = True,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "role": "integrator",
        "status": status,
        "reason": reason,
        "review": {},
        "completion": {"status": "not_run"},
        "metrics": {},
        "head_unchanged": head_unchanged,
    }
