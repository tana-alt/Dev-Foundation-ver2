from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import GitError, git
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.runtime_paths import task_dir


def sync_local_target_branch(
    root: Path,
    *,
    task_id: str,
    remote: str,
    branch: str,
    expected_sha: str,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    old_local_sha = _rev_parse(root, branch)
    git(root, ["fetch", remote, branch], env=env)
    remote_ref = f"refs/remotes/{remote}/{branch}"
    remote_sha = _rev_parse(root, remote_ref)
    result = _base_result(
        task_id=task_id,
        remote=remote,
        branch=branch,
        old_local_sha=old_local_sha,
        remote_sha=remote_sha,
        expected_sha=expected_sha,
    )
    if remote_sha != expected_sha:
        result["status"] = "local_sync_required"
        result["reason"] = "remote_sha_mismatch"
        return _write(root, task_id, result)
    if not _is_ancestor(root, old_local_sha, remote_sha):
        result["status"] = "local_sync_required"
        result["reason"] = "non_fast_forward"
        return _write(root, task_id, result)
    if _current_branch(root) == branch:
        if _dirty(root):
            result["status"] = "local_sync_required"
            result["reason"] = "dirty_worktree"
            return _write(root, task_id, result)
        git(root, ["merge", "--ff-only", remote_ref], env=env)
    else:
        git(root, ["update-ref", f"refs/heads/{branch}", remote_sha, old_local_sha], env=env)
    result["status"] = "local_synced"
    result["reason"] = "ok"
    result["final_local_sha"] = _rev_parse(root, branch)
    return _write(root, task_id, result)


def _base_result(
    *,
    task_id: str,
    remote: str,
    branch: str,
    old_local_sha: str,
    remote_sha: str,
    expected_sha: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "local_sync_required",
        "reason": "not_run",
        "remote": remote,
        "branch": branch,
        "old_local_sha": old_local_sha,
        "remote_sha": remote_sha,
        "expected_sha": expected_sha,
        "final_local_sha": old_local_sha,
    }


def _write(root: Path, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    write_json(task_dir(root, task_id) / "sync-result.json", result)
    return result


def _rev_parse(root: Path, ref: str) -> str:
    return git(root, ["rev-parse", ref]).stdout.strip()


def _current_branch(root: Path) -> str:
    return git(root, ["branch", "--show-current"]).stdout.strip()


def _dirty(root: Path) -> bool:
    lines = git(root, ["status", "--porcelain=v1"]).stdout.splitlines()
    relevant = [line for line in lines if not _ignored_dirty_line(line)]
    return bool(relevant)


def _ignored_dirty_line(line: str) -> bool:
    path = line[3:] if len(line) > 3 else ""
    return path == "artifact/" or path.startswith("artifact/")


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = git(
        root,
        ["merge-base", "--is-ancestor", ancestor, descendant],
        check=False,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise GitError(completed.stderr.strip() or "merge-base failed")
