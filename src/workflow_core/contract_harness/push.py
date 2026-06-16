from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.gitutil import GitError, git
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.policy import decide_external_write, load_policy
from workflow_core.contract_harness.roles import current_role
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.sync import sync_local_target_branch

_ZERO_SHA = "0" * 40


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
        result["lock_ref"] = lock_ref
        result["lock_acquire"] = _existing_remote_lock(root, remote, lock_ref)
        write_json(task_dir(root, task_id) / "push-result.json", result)
        return result, 1
    return _push_with_remote_lock(
        root,
        task_id,
        land_result=land_result,
        remote=remote,
        branch=branch,
        landed_commit=landed_commit,
        lock_ref=lock_ref,
        rescue_ref=rescue_ref,
        remote_sha=remote_sha,
    )


def _push_with_remote_lock(
    root: Path,
    task_id: str,
    *,
    land_result: dict[str, Any],
    remote: str,
    branch: str,
    landed_commit: str,
    lock_ref: str,
    rescue_ref: str,
    remote_sha: str,
) -> tuple[dict[str, Any], int]:
    lock_acquire = _acquire_remote_lock(root, remote, lock_ref, remote_sha)
    if lock_acquire.get("status") != "acquired":
        result = _failure(task_id, land_result, "blocked_by_lock", remote_sha=remote_sha)
        result["status"] = "blocked"
        result["lock_ref"] = lock_ref
        result["lock_acquire"] = lock_acquire
        return _write_result(root, task_id, result, 1)
    result, code = _push_landed_commit(
        root,
        task_id,
        land_result=land_result,
        remote=remote,
        branch=branch,
        landed_commit=landed_commit,
        lock_ref=lock_ref,
        rescue_ref=rescue_ref,
        remote_sha=remote_sha,
        lock_acquire=lock_acquire,
    )
    lock_release = _release_remote_lock(root, remote, lock_ref)
    result["lock_release"] = lock_release
    if lock_release.get("status") != "released":
        result["reason"] = "lock_release_failed"
        code = 1
    return _write_result(root, task_id, result, code)


def _push_landed_commit(
    root: Path,
    task_id: str,
    *,
    land_result: dict[str, Any],
    remote: str,
    branch: str,
    landed_commit: str,
    lock_ref: str,
    rescue_ref: str,
    remote_sha: str,
    lock_acquire: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    rescue_created = False
    try:
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
        result = _success(
            task_id,
            land_result,
            rescue_ref=rescue_ref,
            lock_ref=lock_ref,
            remote_sha_before=remote_sha,
            remote_sha_after=landed_commit,
            lock_acquire=lock_acquire,
            sync=sync,
        )
        return result, 0 if sync.get("status") == "local_synced" else 1
    except (GitError, RuntimeError) as exc:
        result = _failure(task_id, land_result, "push_failed", remote_sha=remote_sha)
        result["rescue_ref"] = rescue_ref if rescue_created else None
        result["lock_ref"] = lock_ref
        result["remote_sha_before"] = remote_sha
        result["lock_acquire"] = lock_acquire
        result["error"] = str(exc)
        return result, 1


def _write_result(
    root: Path,
    task_id: str,
    result: dict[str, Any],
    code: int,
) -> tuple[dict[str, Any], int]:
    write_json(task_dir(root, task_id) / "push-result.json", result)
    return result, code


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


def _acquire_remote_lock(root: Path, remote: str, lock_ref: str, remote_sha: str) -> dict[str, Any]:
    lock_sha = _lock_commit(root, lock_ref=lock_ref, remote_sha=remote_sha)
    completed = git(
        root,
        [
            "push",
            f"--force-with-lease={lock_ref}:{_ZERO_SHA}",
            remote,
            f"{lock_sha}:{lock_ref}",
        ],
        check=False,
    )
    if completed.returncode == 0:
        return {
            "ref": lock_ref,
            "sha": lock_sha,
            "status": "acquired",
            "target_sha": remote_sha,
        }
    if _remote_ref_exists(root, remote, lock_ref):
        return _existing_remote_lock(root, remote, lock_ref)
    return {
        "ref": lock_ref,
        "reason": "remote_lock_acquire_failed",
        "status": "failed",
        "error": completed.stderr.strip() or completed.stdout.strip(),
    }


def _existing_remote_lock(root: Path, remote: str, lock_ref: str) -> dict[str, Any]:
    sha = git(root, ["ls-remote", remote, lock_ref]).stdout.split()[0]
    result = {
        "ref": lock_ref,
        "reason": "remote_lock_exists",
        "sha": sha,
        "status": "blocked",
    }
    target = git(root, ["rev-parse", f"{sha}^"], check=False)
    if target.returncode == 0:
        result["target_sha"] = target.stdout.strip()
    return result


def _lock_commit(root: Path, *, lock_ref: str, remote_sha: str) -> str:
    tree = git(root, ["rev-parse", f"{remote_sha}^{{tree}}"]).stdout.strip()
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid4().hex
    return git(
        root,
        [
            "commit-tree",
            tree,
            "-p",
            remote_sha,
            "-m",
            f"harness push lock {lock_ref} {stamp} {nonce}",
        ],
    ).stdout.strip()


def _release_remote_lock(root: Path, remote: str, lock_ref: str) -> dict[str, Any]:
    completed = git(root, ["push", remote, f":{lock_ref}"], check=False)
    if completed.returncode == 0:
        return {"ref": lock_ref, "status": "released"}
    return {
        "ref": lock_ref,
        "status": "release_failed",
        "error": completed.stderr.strip() or completed.stdout.strip(),
    }


def _rescue_ref(branch: str, task_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"refs/harness/rescue/{branch}/{task_id}/{stamp}"


def _blocked(task_id: str, land_result: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "blocked",
        "reason": "protected_external_write",
        "completed": False,
        **_land_context(land_result),
        "pushed_sha": None,
        "lock_acquire": {
            "reason": "protected_external_write",
            "status": "not_attempted",
        },
        "sync": {
            "reason": "push_not_attempted",
            "status": "not_attempted",
        },
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
        **_land_context(land_result),
        "remote_sha": remote_sha,
        "pushed_sha": None,
    }


def _land_context(land_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "remote": land_result.get("remote"),
        "branch": land_result.get("branch"),
        "target_base_sha": land_result.get("target_base_sha"),
        "landed_commit": land_result.get("landed_commit"),
        "candidate_diff_sha256": land_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": land_result.get("machine_evidence_sha256"),
    }


def _success(
    task_id: str,
    land_result: dict[str, Any],
    *,
    rescue_ref: str,
    lock_ref: str,
    remote_sha_before: str,
    remote_sha_after: str,
    lock_acquire: dict[str, Any],
    sync: dict[str, Any],
) -> dict[str, Any]:
    sync_status = str(sync.get("status") or "")
    return {
        "task_id": task_id,
        "status": "pushed",
        "reason": "ok" if sync_status == "local_synced" else "local_sync_required",
        **_land_context(land_result),
        "pushed_sha": land_result.get("landed_commit"),
        "rescue_ref": rescue_ref,
        "lock_ref": lock_ref,
        "remote_sha_before": remote_sha_before,
        "remote_sha_after": remote_sha_after,
        "lock_acquire": lock_acquire,
        "sync": sync,
    }
