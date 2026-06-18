from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.contract import load_contract, load_verifier_plan
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.land_core import apply_candidate_diff
from workflow_core.contract_harness.policy import (
    decide_external_write,
    integration_target,
    load_policy,
)
from workflow_core.contract_harness.push import _push_with_remote_lock, _rescue_ref
from workflow_core.contract_harness.roles import current_role
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.verifier import all_passed, run_verifiers

_MARKER = ".harness-compose-worktree.json"


def compose_candidates(root: Path, task_ids: list[str]) -> tuple[dict[str, Any], int]:
    if not task_ids:
        raise ValueError("compose requires at least one task_id")
    policy = load_policy(root)
    remote, branch, _branch_policy = integration_target(policy)
    ordered = sorted(set(task_ids))
    git(root, ["fetch", remote, branch])
    target_ref = f"refs/remotes/{remote}/{branch}"
    target_sha = git(root, ["rev-parse", target_ref]).stdout.strip()
    pending = write_pending_index(
        root, ordered, remote=remote, branch=branch, target_sha=target_sha
    )
    worktree_path = _compose_worktree_path(root, remote=remote, branch=branch)
    try:
        worktree = _ensure_compose_worktree(
            root,
            remote=remote,
            branch=branch,
            target_sha=target_sha,
            path=worktree_path,
        )
    except ValueError as exc:
        result = _result(
            root,
            task_ids=ordered,
            remote=remote,
            branch=branch,
            target_sha=target_sha,
            status="blocked",
            reason="compose_worktree_unusable",
            worktree=worktree_path,
            pending=pending,
            green_task_ids=[],
            blamed_task_ids=ordered,
            error=str(exc),
        )
        return _write_compose_result(root, remote, branch, result, code=1)
    return _compose_on_worktree(
        root,
        task_ids=ordered,
        remote=remote,
        branch=branch,
        target_sha=target_sha,
        pending=pending,
        worktree=worktree,
    )


def push_composed_candidates(root: Path, task_ids: list[str]) -> tuple[dict[str, Any], int]:
    compose_result, compose_code = compose_candidates(root, task_ids)
    if compose_code != 0:
        return compose_result, compose_code
    remote = str(compose_result["remote"])
    branch = str(compose_result["branch"])
    policy = load_policy(root)
    decision = decide_external_write(
        policy,
        role=current_role(),
        remote=remote,
        branch=branch,
        action="push_landed_commit",
    )
    if decision.get("ok") is not True:
        return _compose_push_blocked(root, compose_result, decision)
    return _push_green_compose(root, compose_result)


def _compose_on_worktree(
    root: Path,
    *,
    task_ids: list[str],
    remote: str,
    branch: str,
    target_sha: str,
    pending: dict[str, Any],
    worktree: Path,
) -> tuple[dict[str, Any], int]:
    applied: list[str] = []
    for task_id in task_ids:
        result = apply_candidate_diff(root, task_id, worktree)
        if result.returncode != 0:
            return _apply_failed_result(
                root,
                task_ids=task_ids,
                remote=remote,
                branch=branch,
                target_sha=target_sha,
                worktree=worktree,
                pending=pending,
                applied=applied,
                failed_task_id=task_id,
                error=result.stderr.strip() or result.stdout.strip(),
            )
        applied.append(task_id)
    gate = _run_union_gate(worktree, task_ids)
    if gate.get("status") != "pass":
        return _verifier_failed_result(
            root,
            task_ids=task_ids,
            remote=remote,
            branch=branch,
            target_sha=target_sha,
            worktree=worktree,
            pending=pending,
            gate=gate,
        )
    merged_commit = _commit_compose(worktree, task_ids)
    composed = _result(
        root,
        task_ids=task_ids,
        remote=remote,
        branch=branch,
        target_sha=target_sha,
        status="green",
        reason="ok",
        worktree=worktree,
        pending=pending,
        green_task_ids=task_ids,
        blamed_task_ids=[],
        land_gate=gate,
        merged_commit=merged_commit,
    )
    return _write_compose_result(root, remote, branch, composed, code=0)


def _push_green_compose(
    root: Path,
    compose_result: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    remote = str(compose_result["remote"])
    branch = str(compose_result["branch"])
    target_sha = str(compose_result["target_head_sha"])
    git(root, ["fetch", remote, branch])
    remote_sha = git(root, ["rev-parse", f"refs/remotes/{remote}/{branch}"]).stdout.strip()
    if remote_sha != target_sha:
        return _compose_push_not_attempted(
            root, compose_result, "compose_remote_changed", remote_sha
        )
    task_ids = [str(task_id) for task_id in compose_result["green_task_ids"]]
    primary_task_id = task_ids[0]
    land_result = _write_composed_land_results(root, compose_result, task_ids)[primary_task_id]
    pushed, code = _push_with_remote_lock(
        root,
        primary_task_id,
        land_result=land_result,
        remote=remote,
        branch=branch,
        landed_commit=str(compose_result["merged_commit"]),
        lock_ref=f"refs/harness/locks/{remote}/{branch}",
        rescue_ref=_rescue_ref(branch, primary_task_id),
        remote_sha=target_sha,
    )
    result = _compose_push_result(compose_result, pushed, task_ids)
    _write_per_task_push_results(root, result, task_ids)
    return _write_compose_push_result(root, result, code)


def _apply_failed_result(
    root: Path,
    *,
    task_ids: list[str],
    remote: str,
    branch: str,
    target_sha: str,
    worktree: Path,
    pending: dict[str, Any],
    applied: list[str],
    failed_task_id: str,
    error: str,
) -> tuple[dict[str, Any], int]:
    composed = _result(
        root,
        task_ids=task_ids,
        remote=remote,
        branch=branch,
        target_sha=target_sha,
        status="red",
        reason="apply_failed",
        worktree=worktree,
        pending=pending,
        green_task_ids=applied,
        blamed_task_ids=[failed_task_id],
        error=error,
    )
    _write_compose_result(root, remote, branch, composed, code=1)
    _write_rework_request(root, failed_task_id, composed, reason="apply_failed")
    return composed, 1


def _compose_push_blocked(
    root: Path,
    compose_result: dict[str, Any],
    decision: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    result = {
        **compose_result,
        "status": "blocked",
        "reason": "protected_external_write",
        "decision": decision,
        "pushed_sha": None,
        "lock_acquire": {"status": "not_attempted", "reason": "protected_external_write"},
        "lock_release": {"status": "not_attempted", "reason": "protected_external_write"},
    }
    task_ids = [str(task_id) for task_id in compose_result["green_task_ids"]]
    _write_per_task_push_results(root, result, task_ids)
    return _write_compose_push_result(root, result, 1)


def _compose_push_not_attempted(
    root: Path,
    compose_result: dict[str, Any],
    reason: str,
    remote_sha: str,
) -> tuple[dict[str, Any], int]:
    result = {
        **compose_result,
        "status": "escalated",
        "reason": reason,
        "remote_sha": remote_sha,
        "pushed_sha": None,
        "lock_acquire": {"status": "not_attempted", "reason": reason},
        "lock_release": {"status": "not_attempted", "reason": reason},
    }
    task_ids = [str(task_id) for task_id in compose_result["green_task_ids"]]
    _write_per_task_push_results(root, result, task_ids)
    return _write_compose_push_result(root, result, 1)


def _write_composed_land_results(
    root: Path,
    compose_result: dict[str, Any],
    task_ids: list[str],
) -> dict[str, dict[str, Any]]:
    results = {
        task_id: _composed_land_result(root, compose_result, task_id) for task_id in task_ids
    }
    for task_id, result in results.items():
        write_json(task_dir(root, task_id) / "land-result.json", result)
    return results


def _composed_land_result(
    root: Path,
    compose_result: dict[str, Any],
    task_id: str,
) -> dict[str, Any]:
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    return {
        "task_id": task_id,
        "status": "landed",
        "reason": "composed",
        "classification": "COMPOSED",
        "remote": compose_result.get("remote"),
        "branch": compose_result.get("branch"),
        "target_base_sha": compose_result.get("target_head_sha"),
        "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
        "worktree_path": compose_result.get("worktree_path"),
        "landed_commit": compose_result.get("merged_commit"),
        "land_gate": compose_result.get("land_gate"),
        "compose_run_id": compose_result.get("run_id"),
        "composed_task_ids": compose_result.get("task_ids"),
    }


def _compose_push_result(
    compose_result: dict[str, Any],
    pushed: dict[str, Any],
    task_ids: list[str],
) -> dict[str, Any]:
    return {
        **compose_result,
        "status": pushed.get("status"),
        "reason": pushed.get("reason"),
        "pushed_sha": pushed.get("pushed_sha"),
        "remote_sha_before": pushed.get("remote_sha_before"),
        "remote_sha_after": pushed.get("remote_sha_after"),
        "rescue_ref": pushed.get("rescue_ref"),
        "lock_ref": pushed.get("lock_ref"),
        "lock_acquire": pushed.get("lock_acquire"),
        "lock_release": pushed.get("lock_release"),
        "sync": pushed.get("sync"),
        "green_task_ids": task_ids,
    }


def _write_per_task_push_results(
    root: Path,
    compose_push_result: dict[str, Any],
    task_ids: list[str],
) -> None:
    for task_id in task_ids:
        result = {
            **compose_push_result,
            "task_id": task_id,
            "composed_task_ids": task_ids,
            "compose_run_id": compose_push_result.get("run_id"),
        }
        write_json(task_dir(root, task_id) / "push-result.json", result)


def _verifier_failed_result(
    root: Path,
    *,
    task_ids: list[str],
    remote: str,
    branch: str,
    target_sha: str,
    worktree: Path,
    pending: dict[str, Any],
    gate: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    blamed = _localize_verifier_failure(
        root, worktree=worktree, task_ids=task_ids, target_sha=target_sha
    )
    composed = _result(
        root,
        task_ids=task_ids,
        remote=remote,
        branch=branch,
        target_sha=target_sha,
        status="red",
        reason="verifier_failed",
        worktree=worktree,
        pending=pending,
        green_task_ids=[],
        blamed_task_ids=blamed,
        land_gate=gate,
    )
    _write_compose_result(root, remote, branch, composed, code=1)
    for task_id in blamed:
        _write_rework_request(root, task_id, composed, reason="verifier_failed")
    return composed, 1


def write_pending_index(
    root: Path,
    task_ids: list[str],
    *,
    remote: str,
    branch: str,
    target_sha: str,
) -> dict[str, Any]:
    rows = [_pending_row(root, task_id, target_sha=target_sha) for task_id in sorted(set(task_ids))]
    pending = {
        "schema_version": 1,
        "remote": remote,
        "branch": branch,
        "pending": rows,
        "written_by": "harness",
    }
    write_json(_integration_dir(root, remote, branch) / "pending.json", pending)
    return pending


def _pending_row(root: Path, task_id: str, *, target_sha: str) -> dict[str, Any]:
    runtime = task_dir(root, task_id)
    submission = read_json(runtime / "submission.json")
    contract = load_contract(root, task_id)
    return {
        "task_id": task_id,
        "candidate_diff_sha256": submission.get("candidate_diff_sha256"),
        "prepared_base_sha": contract.get("prepared_base_sha"),
        "last_seen_target_sha": target_sha,
        "status": str(submission.get("status") or "submitted"),
        "submitted_at": submission.get("submitted_at"),
    }


def _run_union_gate(path: Path, task_ids: list[str]) -> dict[str, Any]:
    plan = _union_verifier_plan(path, task_ids)
    verifiers = run_verifiers(path, plan)
    passed = all_passed(verifiers)
    return {
        "status": "pass" if passed else "fail",
        "command": "harness composed verifiers: "
        + ", ".join(str(item.get("id", "")) for item in verifiers),
        "exit_code": 0 if passed else 1,
        "verifiers": verifiers,
    }


def _union_verifier_plan(path: Path, task_ids: list[str]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    plan: list[dict[str, Any]] = []
    for task_id in task_ids:
        for verifier in load_verifier_plan(path, task_id):
            key = (str(verifier.get("id")), str(verifier.get("command")))
            if key in seen:
                continue
            seen.add(key)
            plan.append(verifier)
    return plan


def _localize_verifier_failure(
    root: Path,
    *,
    worktree: Path,
    task_ids: list[str],
    target_sha: str,
) -> list[str]:
    blamed: list[str] = []
    for omitted in task_ids:
        _reset_compose_worktree(worktree, target_sha)
        failed_apply = False
        for task_id in task_ids:
            if task_id == omitted:
                continue
            applied = apply_candidate_diff(root, task_id, worktree)
            if applied.returncode != 0:
                failed_apply = True
                break
        if failed_apply:
            continue
        if (
            _run_union_gate(worktree, [task_id for task_id in task_ids if task_id != omitted]).get(
                "status"
            )
            == "pass"
        ):
            blamed.append(omitted)
    _reset_compose_worktree(worktree, target_sha)
    for task_id in task_ids:
        apply_candidate_diff(root, task_id, worktree)
    return blamed or task_ids


def _compose_worktree_path(root: Path, *, remote: str, branch: str) -> Path:
    return runtime_root(root) / "worktrees" / "integration" / _safe(remote) / _safe(branch)


def _ensure_compose_worktree(
    root: Path,
    *,
    remote: str,
    branch: str,
    target_sha: str,
    path: Path,
) -> Path:
    if path.exists():
        if not (path / ".git").exists():
            raise ValueError(f"refusing to reuse non-worktree path: {path}")
        _validate_compose_marker(root, path, remote=remote, branch=branch)
        _refuse_dirty_compose_worktree(path)
        _reset_compose_worktree(path, target_sha)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        git(root, ["worktree", "add", "--detach", str(path), target_sha])
    write_json(
        path / _MARKER,
        {
            "remote": remote,
            "branch": branch,
            "target_sha": target_sha,
            "source_repo_common_dir": str((runtime_root(root).parent).resolve()),
            "written_by": "harness",
        },
    )
    return path


def _validate_compose_marker(root: Path, path: Path, *, remote: str, branch: str) -> None:
    marker = path / _MARKER
    if not marker.is_file():
        raise ValueError(f"refusing to reuse unmarked compose worktree: {path}")
    data = read_json(marker)
    expected_common = str((runtime_root(root).parent).resolve())
    expected = {
        "remote": remote,
        "branch": branch,
        "source_repo_common_dir": expected_common,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f"refusing to reuse compose worktree with mismatched marker: {key}")


def _refuse_dirty_compose_worktree(path: Path) -> None:
    status = git(path, ["status", "--porcelain=v1"]).stdout.strip()
    if status:
        raise ValueError(f"compose worktree is dirty; refusing destructive reuse: {path}")


def _reset_compose_worktree(path: Path, target_sha: str) -> None:
    git(path, ["reset", "--hard", target_sha])
    git(path, ["clean", "-fd"])


def _commit_compose(path: Path, task_ids: list[str]) -> str:
    git(path, ["add", "-A"])
    git(path, ["commit", "-m", "compose " + ", ".join(task_ids)])
    return git(path, ["rev-parse", "HEAD"]).stdout.strip()


def _result(
    root: Path,
    *,
    task_ids: list[str],
    remote: str,
    branch: str,
    target_sha: str,
    status: str,
    reason: str,
    worktree: Path,
    pending: dict[str, Any],
    green_task_ids: list[str],
    blamed_task_ids: list[str],
    land_gate: dict[str, Any] | None = None,
    merged_commit: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    run_id = _run_id(task_ids)
    return {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "reason": reason,
        "remote": remote,
        "branch": branch,
        "target_head_sha": target_sha,
        "task_ids": task_ids,
        "green_task_ids": green_task_ids,
        "blamed_task_ids": blamed_task_ids,
        "pending_sha256": file_hash(_integration_dir(root, remote, branch) / "pending.json"),
        "pending": pending,
        "worktree_path": str(worktree),
        "land_gate": land_gate or {"status": "not_run"},
        "merged_commit": merged_commit,
        "error": error,
        "written_by": "harness",
    }


def _write_compose_result(
    root: Path,
    remote: str,
    branch: str,
    result: dict[str, Any],
    *,
    code: int,
) -> tuple[dict[str, Any], int]:
    integration = _integration_dir(root, remote, branch)
    write_json(integration / "compose-result.json", result)
    write_json(integration / "oracle-runs" / f"{result['run_id']}.json", result)
    return result, code


def _write_compose_push_result(
    root: Path,
    result: dict[str, Any],
    code: int,
) -> tuple[dict[str, Any], int]:
    integration = _integration_dir(root, str(result["remote"]), str(result["branch"]))
    write_json(integration / "compose-push-result.json", result)
    return result, code


def _write_rework_request(
    root: Path,
    task_id: str,
    compose_result: dict[str, Any],
    *,
    reason: str,
) -> None:
    result_path = (
        _integration_dir(root, str(compose_result["remote"]), str(compose_result["branch"]))
        / "compose-result.json"
    )
    request = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "rework_required",
        "reason": reason,
        "blamed_task_ids": [task_id],
        "source_artifact": {
            "type": "compose_result",
            "path": str(result_path),
            "sha256": file_hash(result_path) if result_path.is_file() else None,
        },
        "message_to_writer": _rework_message(reason),
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "rework-request.json", request)


def _rework_message(reason: str) -> str:
    if reason == "apply_failed":
        return "candidate.diff could not be composed with the pending candidate set."
    if reason == "verifier_failed":
        return "the composed candidate set failed machine validation."
    return "compose returned red; inspect compose-result.json."


def _integration_dir(root: Path, remote: str, branch: str) -> Path:
    return runtime_root(root) / "state" / "integration" / _safe(remote) / _safe(branch)


def _run_id(task_ids: list[str]) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"compose-{'-'.join(_safe(task_id) for task_id in task_ids)}-{stamp}-{uuid4().hex[:8]}"


def _safe(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "item"
