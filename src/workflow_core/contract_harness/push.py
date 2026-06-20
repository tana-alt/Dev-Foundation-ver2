from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    record_authority_artifact,
    state_store,
)
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.gitutil import GitError, git
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.merge_oracle import run_single_candidate_oracle
from workflow_core.contract_harness.policy import (
    decide_external_write,
    load_policy,
    max_remote_changed_retries,
)
from workflow_core.contract_harness.roles import current_role
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.sync import sync_local_target_branch

_ZERO_SHA = "0" * 40


def push_task(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    land_result_path = task_dir(root, task_id) / "land-result.json"
    if not land_result_path.is_file():
        result = _precondition_blocked(task_id, {}, "land_result_missing")
        return _write_result(root, task_id, result, 1)
    land_result = read_json(land_result_path)
    if land_result.get("status") != "landed":
        result = _precondition_blocked(task_id, land_result, "land_not_landed")
        return _write_result(root, task_id, result, 1)
    remote, branch, landed_commit = _push_context(land_result)
    policy = load_policy(root)
    decision = _push_decision(policy, remote, branch)
    if decision.get("ok") is not True:
        result = _blocked(task_id, land_result, decision)
        return _write_result(root, task_id, result, 1)
    lock_ref = f"refs/harness/locks/{remote}/{branch}"
    rescue_ref = _rescue_ref(branch, task_id)
    git(root, ["fetch", remote, branch])
    remote_ref = f"refs/remotes/{remote}/{branch}"
    remote_sha = git(root, ["rev-parse", remote_ref]).stdout.strip()
    if remote_sha != land_result.get("target_base_sha"):
        retries = max_remote_changed_retries(policy)
        if retries > 0:
            return _push_remote_changed_with_oracle_retry(
                root,
                task_id,
                land_result=land_result,
                remote=remote,
                branch=branch,
                lock_ref=lock_ref,
                rescue_ref=rescue_ref,
                remote_sha=remote_sha,
                max_retries=retries,
            )
        result = _failure(task_id, land_result, "remote_changed", remote_sha=remote_sha)
        return _write_result(root, task_id, result, 1)
    if _remote_ref_exists(root, remote, lock_ref):
        result = _failure(task_id, land_result, "blocked_by_lock", remote_sha=remote_sha)
        result["status"] = "blocked"
        result["lock_ref"] = lock_ref
        result["lock_acquire"] = _existing_remote_lock(root, remote, lock_ref)
        result["lock_release"] = _not_attempted_lock(lock_ref, "remote_lock_not_acquired")
        return _write_result(root, task_id, result, 1)
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


def _push_remote_changed_with_oracle_retry(
    root: Path,
    task_id: str,
    *,
    land_result: dict[str, Any],
    remote: str,
    branch: str,
    lock_ref: str,
    rescue_ref: str,
    remote_sha: str,
    max_retries: int,
) -> tuple[dict[str, Any], int]:
    attempts: list[dict[str, Any]] = []
    tested_remote_sha = remote_sha
    for attempt in range(1, max_retries + 1):
        oracle_result, oracle_code, latest_remote_sha = _oracle_retry_attempt(
            root,
            task_id,
            remote=remote,
            branch=branch,
            tested_remote_sha=tested_remote_sha,
            attempt_number=attempt,
        )
        attempts.append(_oracle_attempt_summary(oracle_result))
        if oracle_code != 0:
            result = _oracle_red_result(
                task_id,
                land_result,
                oracle_result=oracle_result,
                attempts=attempts,
                remote_sha=tested_remote_sha,
                lock_ref=lock_ref,
            )
            _write_rework_request(root, task_id, result, oracle_result)
            return _write_result(root, task_id, result, 1)
        if latest_remote_sha != tested_remote_sha:
            tested_remote_sha = latest_remote_sha
            continue
        return _push_oracle_green(
            root,
            task_id,
            land_result=land_result,
            oracle_result=oracle_result,
            attempts=attempts,
            remote=remote,
            branch=branch,
            lock_ref=lock_ref,
            rescue_ref=rescue_ref,
            tested_remote_sha=tested_remote_sha,
            attempt=attempt,
        )
    result = _retry_exhausted_result(
        task_id,
        land_result,
        attempts=attempts,
        remote_sha=tested_remote_sha,
        lock_ref=lock_ref,
    )
    return _write_result(root, task_id, result, 1)


def _oracle_retry_attempt(
    root: Path,
    task_id: str,
    *,
    remote: str,
    branch: str,
    tested_remote_sha: str,
    attempt_number: int,
) -> tuple[dict[str, Any], int, str]:
    oracle_result, oracle_code = run_single_candidate_oracle(
        root,
        task_id,
        target_head_sha=tested_remote_sha,
        attempt=attempt_number,
    )
    git(root, ["fetch", remote, branch])
    remote_ref = f"refs/remotes/{remote}/{branch}"
    latest_remote_sha = git(root, ["rev-parse", remote_ref]).stdout.strip()
    return oracle_result, oracle_code, latest_remote_sha


def _push_oracle_green(
    root: Path,
    task_id: str,
    *,
    land_result: dict[str, Any],
    oracle_result: dict[str, Any],
    attempts: list[dict[str, Any]],
    remote: str,
    branch: str,
    lock_ref: str,
    rescue_ref: str,
    tested_remote_sha: str,
    attempt: int,
) -> tuple[dict[str, Any], int]:
    merged_commit = str(oracle_result["merged_commit"])
    oracle_land_result = {
        **land_result,
        "target_base_sha": tested_remote_sha,
        "landed_commit": merged_commit,
        "original_target_base_sha": land_result.get("target_base_sha"),
        "original_landed_commit": land_result.get("landed_commit"),
    }
    result, code = _push_with_remote_lock(
        root,
        task_id,
        land_result=oracle_land_result,
        remote=remote,
        branch=branch,
        landed_commit=merged_commit,
        lock_ref=lock_ref,
        rescue_ref=rescue_ref,
        remote_sha=tested_remote_sha,
    )
    result["oracle_retry"] = {
        "status": oracle_result.get("status"),
        "reason": oracle_result.get("reason"),
        "attempt": attempt,
        "run_id": oracle_result.get("run_id"),
        "target_head_sha": tested_remote_sha,
        "attempts": attempts,
    }
    return _write_result(root, task_id, result, code)


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
        result["lock_release"] = _not_attempted_lock(lock_ref, "remote_lock_not_acquired")
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
    _record_push(root, task_id, result)
    return result, code


def _record_push(root: Path, task_id: str, result: dict[str, Any]) -> None:
    candidate_sha = str(result.get("candidate_diff_sha256") or "")
    status = str(result.get("status") or "")
    phase = WorkflowPhase.PUSHED if status == "pushed" else WorkflowPhase.BLOCKED
    event = record_authority_artifact(
        root,
        task_id,
        "push-result.json",
        event_type="PUSH",
        to_phase=phase,
        payload={
            "candidate_diff_sha256": candidate_sha,
            "machine_evidence_sha256": result.get("machine_evidence_sha256"),
            "status": status,
            "remote_sha_after": result.get("remote_sha_after"),
            "landed_commit": result.get("landed_commit"),
        },
        candidate_id=candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
    )
    if status == "pushed":
        state_store(root).append_event(
            task_id=task_id,
            candidate_id=candidate_id_from_patch_sha256(candidate_sha) if candidate_sha else None,
            event_type="COMPLETE",
            from_phase=WorkflowPhase.PUSHED,
            to_phase=WorkflowPhase.COMPLETE,
            payload={
                "push_event_sha256": event.event_sha256,
                "candidate_diff_sha256": candidate_sha,
                "remote_sha_after": result.get("remote_sha_after"),
                "landed_commit": result.get("landed_commit"),
            },
            actor=os.environ.get("HARNESS_ACTOR") or "harness",
        )


def _push_context(land_result: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(land_result["remote"]),
        str(land_result["branch"]),
        str(land_result["landed_commit"]),
    )


def _push_decision(policy: dict[str, Any], remote: str, branch: str) -> dict[str, Any]:
    return decide_external_write(
        policy,
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
        "lock_release": {
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
        "lock_acquire": {
            "reason": reason,
            "status": "not_attempted",
        },
        "lock_release": {
            "reason": reason,
            "status": "not_attempted",
        },
    }


def _precondition_blocked(
    task_id: str,
    land_result: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "blocked",
        "reason": reason,
        **_land_context(land_result),
        "pushed_sha": None,
        "lock_acquire": {
            "reason": reason,
            "status": "not_attempted",
        },
        "lock_release": {
            "reason": reason,
            "status": "not_attempted",
        },
        "sync": {
            "reason": reason,
            "status": "not_attempted",
        },
    }


def _oracle_red_result(
    task_id: str,
    land_result: dict[str, Any],
    *,
    oracle_result: dict[str, Any],
    attempts: list[dict[str, Any]],
    remote_sha: str,
    lock_ref: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "rework_required",
        "reason": "oracle_red",
        **_land_context(land_result),
        "remote_sha": remote_sha,
        "pushed_sha": None,
        "blamed_task_ids": list(oracle_result.get("blamed_task_ids") or [task_id]),
        "oracle_retry": {
            "status": oracle_result.get("status"),
            "reason": oracle_result.get("reason"),
            "attempt": oracle_result.get("attempt"),
            "run_id": oracle_result.get("run_id"),
            "target_head_sha": oracle_result.get("target_head_sha"),
            "attempts": attempts,
        },
        "lock_acquire": _not_attempted_lock(lock_ref, "oracle_red"),
        "lock_release": _not_attempted_lock(lock_ref, "oracle_red"),
    }


def _retry_exhausted_result(
    task_id: str,
    land_result: dict[str, Any],
    *,
    attempts: list[dict[str, Any]],
    remote_sha: str,
    lock_ref: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "escalated",
        "reason": "oracle_retry_exhausted",
        **_land_context(land_result),
        "remote_sha": remote_sha,
        "pushed_sha": None,
        "oracle_retry": {
            "status": "exhausted",
            "reason": "oracle_retry_exhausted",
            "attempts": attempts,
        },
        "lock_acquire": _not_attempted_lock(lock_ref, "oracle_retry_exhausted"),
        "lock_release": _not_attempted_lock(lock_ref, "oracle_retry_exhausted"),
    }


def _oracle_attempt_summary(oracle_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt": oracle_result.get("attempt"),
        "status": oracle_result.get("status"),
        "reason": oracle_result.get("reason"),
        "run_id": oracle_result.get("run_id"),
        "target_head_sha": oracle_result.get("target_head_sha"),
        "merged_commit": oracle_result.get("merged_commit"),
    }


def _not_attempted_lock(lock_ref: str, reason: str) -> dict[str, Any]:
    return {
        "ref": lock_ref,
        "reason": reason,
        "status": "not_attempted",
    }


def _write_rework_request(
    root: Path,
    task_id: str,
    push_result: dict[str, Any],
    oracle_result: dict[str, Any],
) -> None:
    oracle_path = task_dir(root, task_id) / "oracle-result.json"
    reason = str(oracle_result.get("reason") or "oracle_red")
    request = {
        "schema_version": 1,
        "task_id": task_id,
        "status": "rework_required",
        "reason": reason,
        "blamed_task_ids": push_result.get("blamed_task_ids") or [task_id],
        "source_artifact": {
            "type": "oracle_result",
            "path": str(oracle_path),
            "sha256": file_hash(oracle_path),
        },
        "message_to_writer": _rework_message(reason),
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "rework-request.json", request)


def _rework_message(reason: str) -> str:
    if reason == "apply_failed":
        return (
            "candidate.diff could not be applied to the current remote head. "
            "Rebase the writer work on the latest target and verify/submit again."
        )
    if reason == "verifier_failed":
        return (
            "candidate.diff applied to the current remote head, but machine validation failed. "
            "Inspect oracle-result.json and verify/submit an updated candidate."
        )
    return "merge oracle returned red. Inspect oracle-result.json and resubmit after rework."


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
        "pushed_sha": remote_sha_after,
        "rescue_ref": rescue_ref,
        "lock_ref": lock_ref,
        "remote_sha_before": remote_sha_before,
        "remote_sha_after": remote_sha_after,
        "lock_acquire": lock_acquire,
        "sync": sync,
    }
