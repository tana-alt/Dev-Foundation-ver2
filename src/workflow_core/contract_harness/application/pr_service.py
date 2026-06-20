from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.application.services import (
    candidate_id_from_patch_sha256,
    latest_event_payload,
    record_authority_artifact,
)
from workflow_core.contract_harness.contract import load_verifier_plan
from workflow_core.contract_harness.domain.models import WorkflowPhase
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.hashing import sha256_text
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.submission import validate_submission
from workflow_core.contract_harness.verifier import all_passed, run_verifiers
from workflow_core.contract_harness.worktree import create_worktree


def create_local_pr(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    submission = validate_submission(root, task_id)
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    candidate_sha = str(submission["candidate_diff_sha256"])
    candidate_id = candidate_id_from_patch_sha256(candidate_sha)
    worktree = create_worktree(root, task_id, kind="reviewer", reviewer_id=f"pr-{candidate_id}")
    path = Path(str(worktree["path"]))
    git(path, ["add", "-A"])
    committed = git(
        path,
        ["commit", "-m", f"harness pr {task_id} {candidate_id}"],
        check=False,
    )
    if committed.returncode != 0:
        result = _result(
            task_id,
            candidate_id=candidate_id,
            status="failed",
            reason=committed.stderr.strip() or "commit_failed",
            ref=_pr_ref(task_id, candidate_id),
            head_sha=None,
            base_sha=str(verify_result["base_sha"]),
            candidate_diff_sha256=candidate_sha,
            diff_sha256=None,
            worktree_path=path,
        )
        write_json(task_dir(root, task_id) / "pr-result.json", result)
        return result, 1
    head_sha = git(path, ["rev-parse", "HEAD"]).stdout.strip()
    ref = _pr_ref(task_id, candidate_id)
    git(root, ["update-ref", ref, head_sha])
    diff_sha = _diff_hash(path, str(verify_result["base_sha"]), head_sha)
    status = "created" if diff_sha == candidate_sha else "failed"
    reason = "ok" if status == "created" else "candidate_hash_mismatch"
    result = _result(
        task_id,
        candidate_id=candidate_id,
        status=status,
        reason=reason,
        ref=ref,
        head_sha=head_sha,
        base_sha=str(verify_result["base_sha"]),
        candidate_diff_sha256=candidate_sha,
        diff_sha256=diff_sha,
        worktree_path=path,
    )
    write_json(task_dir(root, task_id) / "pr-result.json", result)
    if status == "created":
        record_authority_artifact(
            root,
            task_id,
            "pr-result.json",
            event_type="PR_CREATED",
            to_phase=WorkflowPhase.PR_CREATED,
            payload={
                "candidate_diff_sha256": candidate_sha,
                "pr_head_sha": head_sha,
                "base_sha": verify_result["base_sha"],
                "ref": ref,
            },
            candidate_id=candidate_id,
        )
    return result, 0 if status == "created" else 1


def check_local_pr(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    created = latest_event_payload(root, task_id, "PR_CREATED")
    if created is None:
        result = {
            "task_id": task_id,
            "status": "blocked",
            "reason": "pr_not_created",
            "ref": None,
            "written_by": "harness",
        }
        write_json(task_dir(root, task_id) / "pr-check-result.json", result)
        return result, 1
    ref = str(created["ref"])
    base_sha = str(created["base_sha"])
    candidate_sha = str(created["candidate_diff_sha256"])
    candidate_id = candidate_id_from_patch_sha256(candidate_sha)
    current_head = _ref_head(root, ref)
    diff_sha = _diff_hash(root, base_sha, current_head) if current_head is not None else None
    if current_head is None or diff_sha != candidate_sha:
        result = _check_result(
            task_id,
            candidate_id=candidate_id,
            status="blocked",
            reason="pr_ref_hash_mismatch",
            ref=ref,
            head_sha=current_head,
            base_sha=base_sha,
            candidate_diff_sha256=candidate_sha,
            diff_sha256=diff_sha,
            verifiers=[],
        )
        write_json(task_dir(root, task_id) / "pr-check-result.json", result)
        return result, 1
    path = _pr_check_worktree(root, task_id, candidate_id, current_head)
    verifiers = run_verifiers(path, load_verifier_plan(path, task_id))
    passed = all_passed(verifiers)
    result = _check_result(
        task_id,
        candidate_id=candidate_id,
        status="pass" if passed else "fail",
        reason="ok" if passed else "verifier_failed",
        ref=ref,
        head_sha=current_head,
        base_sha=base_sha,
        candidate_diff_sha256=candidate_sha,
        diff_sha256=diff_sha,
        verifiers=verifiers,
    )
    write_json(task_dir(root, task_id) / "pr-check-result.json", result)
    if passed:
        record_authority_artifact(
            root,
            task_id,
            "pr-check-result.json",
            event_type="PR_CHECKED",
            to_phase=WorkflowPhase.PR_CHECKED,
            payload={
                "candidate_diff_sha256": candidate_sha,
                "pr_head_sha": current_head,
                "base_sha": base_sha,
                "ref": ref,
            },
            candidate_id=candidate_id,
        )
    return result, 0 if passed else 1


def validate_local_pr_checked(root: Path, task_id: str, candidate_sha: str) -> dict[str, Any]:
    created = latest_event_payload(root, task_id, "PR_CREATED")
    if created is None:
        return {"status": "not_required", "reason": "local_pr_not_created"}
    candidate_id = candidate_id_from_patch_sha256(candidate_sha)
    checked = latest_event_payload(root, task_id, "PR_CHECKED", candidate_id=candidate_id)
    if checked is None:
        return {
            "status": "blocked",
            "reason": "pr_checks_missing",
            "ref": created.get("ref"),
        }
    ref = str(checked["ref"])
    base_sha = str(checked["base_sha"])
    current_head = _ref_head(root, ref)
    diff_sha = _diff_hash(root, base_sha, current_head) if current_head is not None else None
    if (
        current_head is None
        or current_head != checked.get("pr_head_sha")
        or checked.get("candidate_diff_sha256") != candidate_sha
        or diff_sha != candidate_sha
    ):
        return {
            "status": "blocked",
            "reason": "pr_check_stale",
            "ref": ref,
            "head_sha": current_head,
            "checked_head_sha": checked.get("pr_head_sha"),
            "candidate_diff_sha256": candidate_sha,
            "diff_sha256": diff_sha,
        }
    return {
        "status": "pass",
        "reason": "ok",
        "ref": ref,
        "head_sha": current_head,
        "candidate_diff_sha256": candidate_sha,
    }


def _result(
    task_id: str,
    *,
    candidate_id: str,
    status: str,
    reason: str,
    ref: str,
    head_sha: str | None,
    base_sha: str,
    candidate_diff_sha256: str,
    diff_sha256: str | None,
    worktree_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id,
        "status": status,
        "reason": reason,
        "ref": ref,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "candidate_diff_sha256": candidate_diff_sha256,
        "diff_sha256": diff_sha256,
        "worktree_path": str(worktree_path),
        "written_by": "harness",
    }


def _pr_ref(task_id: str, candidate_id: str) -> str:
    return f"refs/harness/pr/{_ref_component(task_id)}/{_ref_component(candidate_id)}"


def _ref_component(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value)
    return cleaned.strip(".-") or "task"


def _check_result(
    task_id: str,
    *,
    candidate_id: str,
    status: str,
    reason: str,
    ref: str,
    head_sha: str | None,
    base_sha: str,
    candidate_diff_sha256: str,
    diff_sha256: str | None,
    verifiers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "candidate_id": candidate_id,
        "status": status,
        "reason": reason,
        "ref": ref,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "candidate_diff_sha256": candidate_diff_sha256,
        "diff_sha256": diff_sha256,
        "verifiers": verifiers,
        "written_by": "harness",
    }


def _ref_head(root: Path, ref: str) -> str | None:
    completed = git(root, ["rev-parse", "--verify", ref], check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _pr_check_worktree(root: Path, task_id: str, candidate_id: str, head_sha: str) -> Path:
    path = runtime_root(root) / "worktrees" / task_id / "pr-checks" / candidate_id
    if path.exists():
        if not (path / ".git").exists():
            raise ValueError(f"refusing to reuse non-worktree path: {path}")
        git(path, ["reset", "--hard"])
        git(path, ["clean", "-fd"])
        git(path, ["checkout", "--detach", head_sha])
        git(path, ["reset", "--hard", head_sha])
        git(path, ["clean", "-fd"])
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    git(root, ["worktree", "add", "--detach", str(path), head_sha])
    return path


def _diff_hash(path: Path, base_sha: str, head_sha: str) -> str:
    diff = git(
        path,
        [
            "-c",
            "core.autocrlf=false",
            "-c",
            "diff.noprefix=false",
            "-c",
            "diff.renames=false",
            "diff",
            "--binary",
            "--full-index",
            base_sha,
            head_sha,
        ],
    ).stdout
    return sha256_text(diff)
