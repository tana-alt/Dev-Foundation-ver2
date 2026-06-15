from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import GitError, git
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.policy import decide_external_write, load_policy
from workflow_core.contract_harness.roles import current_role
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.sync import sync_local_target_branch


def push_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    land_result, remote, branch, landed_commit = _push_context(root, task_id)
    decision = _push_decision(root, remote, branch)
    if decision.get("ok") is not True:
        result = _blocked(task_id, land_result, decision)
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 1
    lock_ref = f"refs/harness/locks/{remote}/{branch}"
    rescue_ref = _rescue_ref(branch, task_id)
    git(root, ["fetch", remote, branch])
    remote_ref = f"refs/remotes/{remote}/{branch}"
    remote_sha = git(root, ["rev-parse", remote_ref]).stdout.strip()
    if remote_sha != land_result.get("target_base_sha"):
        result = _failure(task_id, land_result, "remote_changed", remote_sha=remote_sha)
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 1
    if _remote_ref_exists(root, remote, lock_ref):
        result = _failure(task_id, land_result, "blocked_by_lock", remote_sha=remote_sha)
        result["status"] = "blocked"
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 1
    acquired = False
    rescue_created = False
    try:
        git(root, ["push", remote, f"{remote_sha}:{lock_ref}"])
        acquired = True
        git(root, ["push", remote, f"{remote_sha}:{rescue_ref}"])
        rescue_created = True
        git(root, ["push", remote, f"{landed_commit}:refs/heads/{branch}"])
        sync = sync_local_target_branch(
            root,
            task_id=task_id,
            remote=remote,
            branch=branch,
            expected_sha=landed_commit,
        )
        result = _success(task_id, land_result, rescue_ref=rescue_ref, sync=sync)
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 0 if sync.get("status") == "local_synced" else 1
    except (GitError, RuntimeError) as exc:
        result = _failure(task_id, land_result, "push_failed", remote_sha=remote_sha)
        result["rescue_ref"] = rescue_ref if rescue_created else None
        result["lock_ref"] = lock_ref
        result["error"] = str(exc)
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 1
    finally:
        if acquired:
            git(root, ["push", remote, f":{lock_ref}"], check=False)


def _push_context(root: Path, task_id: str) -> tuple[dict[str, Any], str, str, str]:
    land_result = read_json(task_dir(root, task_id) / "land-result.json")
    if land_result.get("status") != "landed":
        raise ValueError("land-result must be landed before push")
    return (
        land_result,
        str(land_result["remote"]),
        str(land_result["branch"]),
        str(land_result["landed_commit"]),
    )


def _push_decision(root: Path, remote: str, branch: str) -> dict[str, Any]:
    return decide_external_write(
        load_policy(root),
        role=current_role(),
        remote=remote,
        branch=branch,
        action="push_landed_commit",
    )


def _remote_ref_exists(root: Path, remote: str, ref: str) -> bool:
    return bool(git(root, ["ls-remote", "--exit-code", remote, ref], check=False).stdout.strip())


def _rescue_ref(branch: str, task_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"refs/harness/rescue/{branch}/{task_id}/{stamp}"


def _blocked(task_id: str, land_result: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "blocked",
        "reason": "protected_external_write",
        "completed": False,
        "remote": land_result.get("remote"),
        "branch": land_result.get("branch"),
        "pushed_sha": None,
        "decision": decision,
    }


def _failure(
    task_id: str,
    land_result: dict[str, Any],
    reason: str,
    *,
    remote_sha: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "failed",
        "reason": reason,
        "remote": land_result.get("remote"),
        "branch": land_result.get("branch"),
        "target_base_sha": land_result.get("target_base_sha"),
        "remote_sha": remote_sha,
        "pushed_sha": None,
    }


def _success(
    task_id: str,
    land_result: dict[str, Any],
    *,
    rescue_ref: str,
    sync: dict[str, Any],
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "pushed",
        "reason": "ok",
        "remote": land_result.get("remote"),
        "branch": land_result.get("branch"),
        "target_base_sha": land_result.get("target_base_sha"),
        "pushed_sha": land_result.get("landed_commit"),
        "rescue_ref": rescue_ref,
        "sync": sync,
    }
