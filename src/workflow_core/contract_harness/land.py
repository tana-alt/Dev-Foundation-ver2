from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, cast

from workflow_core.contract_harness.affected import classify_affected_set
from workflow_core.contract_harness.contract import load_verifier_plan
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.lock import LockBlocked, local_lock
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.submission import validate_submission
from workflow_core.contract_harness.verifier import all_passed, run_verifiers
from workflow_core.contract_harness.worktree import create_worktree


def land_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    validate_submission(root, task_id)
    gate_result = read_json(task_dir(root, task_id) / "gate-result.json")
    if gate_result.get("mergeable") is not True:
        raise ValueError("gate-result must be mergeable before land")
    policy = load_policy(root)
    _remote, branch, _branch_policy = integration_target(policy)
    affected = classify_affected_set(root, task_id)
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
    except LockBlocked:
        result = _result(root, task_id, affected, status="blocked", reason="blocked_by_lock")
        code = 1
    write_json(task_dir(root, task_id) / "land-result.json", result)
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
    candidate = task_dir(root, task_id) / "candidate.diff"
    applied = git(path, ["apply", "--whitespace=nowarn", str(candidate)], check=False)
    return applied.returncode == 0


def _run_machine_gate(path: Path, task_id: str) -> dict[str, Any]:
    if "FOUNDATION_GATE_TIER" not in os.environ:
        verifiers = run_verifiers(path, load_verifier_plan(path, task_id))
        passed = all_passed(verifiers)
        return {
            "status": "pass" if passed else "fail",
            "command": "harness verifiers: "
            + ", ".join(str(item.get("id", "")) for item in verifiers),
            "exit_code": 0 if passed else 1,
            "verifiers": verifiers,
        }
    tier = os.environ.get("FOUNDATION_GATE_TIER", "check-required")
    completed = subprocess.run(
        ["make", tier],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("FOUNDATION_GATE_TIMEOUT_S", "900")),
    )
    return {
        "status": "pass" if completed.returncode == 0 else "fail",
        "command": f"make {tier}",
        "exit_code": completed.returncode,
    }


def _commit_land(path: Path, task_id: str) -> str:
    git(path, ["add", "-A"])
    git(path, ["commit", "-m", f"land {task_id}"])
    return git(path, ["rev-parse", "HEAD"]).stdout.strip()


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
) -> dict[str, Any]:
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    return {
        "task_id": task_id,
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
    }


def _lock_timeout(policy: dict[str, Any]) -> int:
    bottlenecks = _mapping(policy.get("bottlenecks"))
    integration = _mapping(bottlenecks.get("integration"))
    return int(integration.get("lock_timeout_s", 900))


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}
