from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import task_dir


def check_manual_resolution(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    runtime = task_dir(root, task_id)
    resolved_diff = runtime / "resolved.diff"
    metadata = runtime / "resolved-diff.json"
    if not resolved_diff.is_file() or not metadata.is_file():
        return _write_result(
            root,
            task_id,
            status="blocked",
            reason="resolved_diff_required",
            authority=False,
        )
    try:
        data = read_json(metadata)
        reason = _invalid_reason(root, task_id, resolved_diff, data)
    except (OSError, ValueError, KeyError) as exc:
        reason = str(exc)
        data = {}
    if reason is not None:
        return _write_result(
            root,
            task_id,
            status="blocked",
            reason=reason,
            authority=False,
            metadata=data,
        )
    return _write_result(
        root,
        task_id,
        status="validated",
        reason="ok",
        authority=True,
        metadata=data,
    )


def _invalid_reason(
    root: Path,
    task_id: str,
    resolved_diff: Path,
    data: dict[str, Any],
) -> str | None:
    if data.get("task_id") != task_id:
        return "task_id_mismatch"
    if data.get("source") != "manual_integrator_resolution":
        return "invalid_source"
    candidate = task_dir(root, task_id) / "candidate.diff"
    if not candidate.is_file() or data.get("candidate_diff_sha256") != file_hash(candidate):
        return "candidate_diff_hash_mismatch"
    if data.get("resolved_diff_sha256") != file_hash(resolved_diff):
        return "resolved_diff_hash_mismatch"
    validation = data.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "pass":
        return "machine_validation_required"
    review_impact = data.get("review_impact")
    if isinstance(review_impact, dict) and review_impact.get("requires_reapproval") is True:
        reapproval = data.get("review_reapproval")
        if not isinstance(reapproval, dict) or reapproval.get("status") != "approved":
            return "review_reapproval_required"
    return None


def _write_result(
    root: Path,
    task_id: str,
    *,
    status: str,
    reason: str,
    authority: bool,
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    result = {
        "schema_version": 1,
        "task_id": task_id,
        "status": status,
        "reason": reason,
        "authority": authority,
        "metadata": metadata or {},
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "manual-resolution-result.json", result)
    return result, 0 if authority else 1
