from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.affected import classify_affected_set
from workflow_core.contract_harness.application.pr_service import validate_local_pr_checked
from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
)
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.land_core import (
    apply_candidate_diff,
    commit_land,
    run_machine_gate,
)
from workflow_core.contract_harness.lock import LockBlocked, local_lock
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.submission import validate_submission
from workflow_core.contract_harness.sync import sync_landed_local_target_branch
from workflow_core.contract_harness.worktree import cleanup_task_worktrees, create_worktree


def land_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    submission = validate_submission(root, task_id)
    policy = load_policy(root)
    _remote, branch, _branch_policy = integration_target(policy)
    affected = classify_affected_set(root, task_id)
    gate_result_path = task_dir(root, task_id) / "gate-result.json"
    if not gate_result_path.is_file():
        result = _result(root, task_id, affected, status="blocked", reason="gate_result_missing")
        write_json(task_dir(root, task_id) / "land-result.json", result)
        _record_land(root, task_id, result)
        return result, 1
    gate_result = read_json(gate_result_path)
    if gate_result.get("mergeable") is not True:
        result = _result(
            root,
            task_id,
            affected,
            status="blocked",
            reason="gate_not_mergeable",
            gate_result=gate_result,
        )
        write_json(task_dir(root, task_id) / "land-result.json", result)
        _record_land(root, task_id, result)
        return result, 1
    pr_check = validate_local_pr_checked(root, task_id, str(submission["candidate_diff_sha256"]))
    if pr_check.get("status") == "blocked":
        result = _result(
            root,
            task_id,
            affected,
            status="blocked",
            reason=str(pr_check["reason"]),
            gate_result=gate_result,
            pr_check=pr_check,
        )
        write_json(task_dir(root, task_id) / "land-result.json", result)
        _record_land(root, task_id, result)
        return result, 1
    timeout_s = _lock_timeout(policy)
    try:
        with local_lock(
            root,
            "land",
            task_id=task_id,
            target_branch=branch,
            base_sha=str(affected["target_sha"]),
            timeout_s=timeout_s,
        ):
            result, code = _land_with_lock(root, task_id, affected)
    except LockBlocked as exc:
        result = _result(root, task_id, affected, status="blocked", reason="blocked_by_lock")
        result["lock"] = exc.diagnostics
        code = 1
    if result.get("status") == "landed":
        result, code = _finalize_landed(root, task_id, branch, result, code)
    write_json(task_dir(root, task_id) / "land-result.json", result)
    _record_land(root, task_id, result)
    return result, code


def _land_with_lock(
    root: Path, task_id: str, affected: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    worktree = create_worktree(root, task_id, kind="integrator")
    path = Path(str(worktree["path"]))
    if affected["classification"] == "REBASE":
        return _rework_result(root, task_id, affected, "rebase_required", path)
    if not _apply_candidate(root, task_id, path):
        return _rework_result(root, task_id, affected, "candidate_apply_failed", path)
    land_gate = _run_machine_gate(path, task_id)
    if land_gate["status"] != "pass":
        return _rework_result(
            root,
            task_id,
            affected,
            "machine_gate_failed",
            path,
            land_gate=land_gate,
        )
    landed_commit = _commit_land(path, task_id)
    return (
        _result(
            root,
            task_id,
            affected,
            status="landed",
            reason="ok",
            worktree_path=path,
            landed_commit=landed_commit,
            land_gate=land_gate,
        ),
        0,
    )


def _finalize_landed(
    root: Path,
    task_id: str,
    branch: str,
    result: dict[str, Any],
    code: int,
) -> tuple[dict[str, Any], int]:
    landed_commit = str(result.get("landed_commit") or "")
    sync = sync_landed_local_target_branch(
        root,
        task_id=task_id,
        branch=branch,
        landed_commit=landed_commit,
    )
    cleanup = cleanup_task_worktrees(root, task_id)
    result = {**result, "local_main_sync": sync, "worktree_cleanup": cleanup}
    if sync.get("status") != "local_synced" or cleanup.get("status") != "pass":
        result["reason"] = str(sync.get("reason") or cleanup.get("status") or "finalize_failed")
        return result, 1
    return result, code


def _rework_result(
    root: Path,
    task_id: str,
    affected: dict[str, Any],
    reason: str,
    worktree_path: Path,
    land_gate: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    return (
        _result(
            root,
            task_id,
            affected,
            status="rework_required",
            reason=reason,
            worktree_path=worktree_path,
            land_gate=land_gate,
        ),
        1,
    )


def _apply_candidate(root: Path, task_id: str, path: Path) -> bool:
    applied = apply_candidate_diff(root, task_id, path)
    return applied.returncode == 0


def _run_machine_gate(path: Path, task_id: str) -> dict[str, Any]:
    return run_machine_gate(path, task_id)


def _commit_land(path: Path, task_id: str) -> str:
    return commit_land(path, task_id)


def _result(
    root: Path,
    task_id: str,
    affected: dict[str, Any],
    *,
    status: str,
    reason: str,
    worktree_path: Path | None = None,
    landed_commit: str | None = None,
    land_gate: dict[str, Any] | None = None,
    gate_result: dict[str, Any] | None = None,
    pr_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    return {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id_from_patch_sha256(
            str(verify_result.get("candidate_diff_sha256") or "")
        ),
        "status": status,
        "reason": reason,
        "classification": affected.get("classification"),
        "remote": affected.get("remote"),
        "branch": affected.get("branch"),
        "target_base_sha": affected.get("target_sha"),
        "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
        "worktree_path": str(worktree_path) if worktree_path else None,
        "landed_commit": landed_commit,
        "land_gate": land_gate or {"status": "not_run"},
        "gate_result": gate_result,
        "pr_check": pr_check or {"status": "not_required"},
    }


def _record_land(root: Path, task_id: str, result: dict[str, Any]) -> None:
    candidate_sha = str(result.get("candidate_diff_sha256") or "")
    phase = WorkflowPhase.LANDED if result.get("status") == "landed" else WorkflowPhase.BLOCKED
    record_authority_artifact(
        root,
        task_id,
        "land-result.json",
        event_type="LAND",
        to_phase=phase,
        payload={
            "candidate_diff_sha256": candidate_sha,
            "machine_evidence_sha256": result.get("machine_evidence_sha256"),
            "status": result.get("status"),
            "landed_commit": result.get("landed_commit"),
            "local_main_sync": result.get("local_main_sync"),
            "worktree_cleanup": result.get("worktree_cleanup"),
        },
        candidate_id=candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
    )


def _lock_timeout(policy: dict[str, Any]) -> int:
    bottlenecks = _mapping(policy.get("bottlenecks"))
    integration = _mapping(bottlenecks.get("integration"))
    return int(integration.get("lock_timeout_s", 900))


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}
