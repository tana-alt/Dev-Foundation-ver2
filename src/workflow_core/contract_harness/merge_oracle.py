from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from workflow_core.contract_harness.evidence import artifact_hashes
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.land_core import (
    apply_candidate_diff,
    commit_land,
    run_machine_gate,
)
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.verify import recompute_machine_evidence
from workflow_core.contract_harness.worktree import create_worktree


def run_single_candidate_oracle(
    root: Path,
    task_id: str,
    *,
    target_head_sha: str,
    attempt: int = 1,
) -> tuple[dict[str, Any], int]:
    policy = load_policy(root)
    remote, branch, _branch_policy = integration_target(policy)
    run_id = _run_id(task_id, attempt)
    base = _base_result(
        task_id,
        remote=remote,
        branch=branch,
        target_head_sha=target_head_sha,
        attempt=attempt,
        run_id=run_id,
    )
    try:
        submission, verify_result = _validate_submission_artifacts(root, task_id)
    except (OSError, ValueError, KeyError) as exc:
        result = {
            **base,
            "status": "red",
            "reason": str(exc),
            "blamed_task_ids": [task_id],
            "submission": None,
            "land_gate": {"status": "not_run"},
        }
        return _write_results(root, task_id, result, code=1)
    return _run_validated_oracle(
        root,
        task_id,
        base=base,
        submission=submission,
        verify_result=verify_result,
        target_head_sha=target_head_sha,
    )


def _run_validated_oracle(
    root: Path,
    task_id: str,
    *,
    base: dict[str, Any],
    submission: dict[str, Any],
    verify_result: dict[str, Any],
    target_head_sha: str,
) -> tuple[dict[str, Any], int]:
    candidate_sha = str(submission["candidate_diff_sha256"])
    result_base = {
        **base,
        "candidate_diff_sha256": candidate_sha,
        "machine_evidence_sha256": verify_result.get("machine_evidence_sha256"),
    }
    worktree = create_worktree(root, task_id, kind="integrator")
    path = Path(str(worktree["path"]))
    git(path, ["reset", "--hard", target_head_sha])
    git(path, ["clean", "-fd"])

    applied = apply_candidate_diff(root, task_id, path)
    if applied.returncode != 0:
        result = _oracle_result(
            result_base,
            status="red",
            reason="apply_failed",
            blamed_task_ids=[task_id],
            worktree_path=path,
            land_gate={"status": "not_run"},
            error=applied.stderr.strip() or applied.stdout.strip(),
        )
        return _write_results(root, task_id, result, code=1)

    land_gate = run_machine_gate(path, task_id)
    if land_gate.get("status") != "pass":
        result = _oracle_result(
            result_base,
            status="red",
            reason="verifier_failed",
            blamed_task_ids=[task_id],
            worktree_path=path,
            land_gate=land_gate,
        )
        return _write_results(root, task_id, result, code=1)

    merged_commit = commit_land(path, task_id)
    result = _oracle_result(
        result_base,
        status="green",
        reason="ok",
        blamed_task_ids=[],
        worktree_path=path,
        land_gate=land_gate,
        merged_commit=merged_commit,
    )
    return _write_results(root, task_id, result, code=0)


def _oracle_result(
    base: dict[str, Any],
    *,
    status: str,
    reason: str,
    blamed_task_ids: list[str],
    worktree_path: Path,
    land_gate: dict[str, Any],
    merged_commit: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    result = {
        **base,
        "status": status,
        "reason": reason,
        "blamed_task_ids": blamed_task_ids,
        "worktree_path": str(worktree_path),
        "land_gate": land_gate,
        "merged_commit": merged_commit,
    }
    if error is not None:
        result["error"] = error
    return result


def _validate_submission_artifacts(
    root: Path,
    task_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = task_dir(root, task_id)
    submission = read_json(runtime / "submission.json")
    verify_result = read_json(runtime / "verify-result.json")
    candidate = runtime / "candidate.diff"
    candidate_sha = file_hash(candidate)
    if submission.get("status") != "submitted":
        raise ValueError("submission status must be submitted")
    if verify_result.get("status") != "pass":
        raise ValueError("verify-result status must be pass")
    if verify_result.get("machine_evidence_sha256") != recompute_machine_evidence(verify_result):
        raise ValueError("machine evidence mismatch")
    if candidate_sha != verify_result.get("candidate_diff_sha256"):
        raise ValueError("candidate_hash_mismatch")
    if candidate_sha != submission.get("candidate_diff_sha256"):
        raise ValueError("candidate_hash_mismatch")
    if submission.get("machine_evidence_sha256") != verify_result.get("machine_evidence_sha256"):
        raise ValueError("machine evidence mismatch")
    if not _matches_artifact_hashes(root, task_id, submission):
        raise ValueError("submission artifact hash mismatch")
    return submission, verify_result


def _matches_artifact_hashes(root: Path, task_id: str, submission: dict[str, Any]) -> bool:
    return all(
        submission.get(key) == value for key, value in artifact_hashes(root, task_id).items()
    )


def _base_result(
    task_id: str,
    *,
    remote: str,
    branch: str,
    target_head_sha: str,
    attempt: int,
    run_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "remote": remote,
        "branch": branch,
        "target_head_sha": target_head_sha,
        "attempt": attempt,
        "run_id": run_id,
        "candidate_diff_sha256": None,
        "machine_evidence_sha256": None,
        "merged_commit": None,
        "written_by": "harness",
    }


def _write_results(
    root: Path,
    task_id: str,
    result: dict[str, Any],
    *,
    code: int,
) -> tuple[dict[str, Any], int]:
    write_json(task_dir(root, task_id) / "oracle-result.json", result)
    write_json(_oracle_run_path(root, result), result)
    return result, code


def _oracle_run_path(root: Path, result: dict[str, Any]) -> Path:
    remote = _safe_component(str(result["remote"]))
    branch = _safe_component(str(result["branch"]))
    run_id = _safe_component(str(result["run_id"]))
    return (
        runtime_root(root)
        / "state"
        / "integration"
        / remote
        / branch
        / "oracle-runs"
        / f"{run_id}.json"
    )


def _run_id(task_id: str, attempt: int) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{_safe_component(task_id)}-attempt-{attempt}-{stamp}-{uuid4().hex[:8]}"


def _safe_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "item"
