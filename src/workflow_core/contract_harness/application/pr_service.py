from __future__ import annotations

import json
import os
import re
import subprocess
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
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.post_review_gate import (
    ensure_post_review_gate_passed,
    post_review_gate_passed_for_candidate,
)
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.submission import validate_submission
from workflow_core.contract_harness.verifier import all_passed, run_verifiers
from workflow_core.contract_harness.worktree import create_worktree


def create_local_pr(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    post_gate, post_gate_code = ensure_post_review_gate_passed(root, task_id)
    if post_gate_code != 0:
        return post_gate, post_gate_code
    submission = validate_submission(root, task_id)
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    candidate_sha = str(submission["candidate_diff_sha256"])
    candidate_id = candidate_id_from_patch_sha256(candidate_sha)
    prepared, prepare_code = _prepare_pr_ref(
        root,
        task_id,
        candidate_id=candidate_id,
        candidate_sha=candidate_sha,
        base_sha=str(verify_result["base_sha"]),
    )
    if prepare_code != 0:
        return prepared, prepare_code
    published = _publish_external_pr(
        root,
        Path(str(prepared["worktree_path"])),
        task_id,
        candidate_id,
        candidate_sha,
    )
    if published["status"] != "created":
        return _write_external_pr_blocked(root, task_id, prepared, published), 1
    result = {**prepared, "status": "created", "reason": "ok", "external_pr": published}
    write_json(task_dir(root, task_id) / "pr-result.json", result)
    _record_pr_created(
        root,
        task_id,
        candidate_id,
        candidate_sha,
        str(prepared["head_sha"]),
        verify_result,
        str(prepared["ref"]),
        external_pr=published,
    )
    return result, 0


def _prepare_pr_ref(
    root: Path,
    task_id: str,
    *,
    candidate_id: str,
    candidate_sha: str,
    base_sha: str,
) -> tuple[dict[str, Any], int]:
    worktree = create_worktree(root, task_id, kind="reviewer", reviewer_id=f"pr-{candidate_id}")
    path = Path(str(worktree["path"]))
    committed = _commit_pr_worktree(path, task_id, candidate_id)
    if committed.returncode != 0:
        return _write_pr_result(
            root,
            task_id,
            candidate_id=candidate_id,
            status="failed",
            reason=committed.stderr.strip() or "commit_failed",
            ref=_pr_ref(task_id, candidate_id),
            head_sha=None,
            base_sha=base_sha,
            candidate_diff_sha256=candidate_sha,
            diff_sha256=None,
            worktree_path=path,
        ), 1
    head_sha = git(path, ["rev-parse", "HEAD"]).stdout.strip()
    ref = _pr_ref(task_id, candidate_id)
    git(root, ["update-ref", ref, head_sha])
    diff_sha = _diff_hash(path, base_sha, head_sha)
    if diff_sha != candidate_sha:
        result = _result(
            task_id,
            candidate_id=candidate_id,
            status="failed",
            reason="candidate_hash_mismatch",
            ref=ref,
            head_sha=head_sha,
            base_sha=base_sha,
            candidate_diff_sha256=candidate_sha,
            diff_sha256=diff_sha,
            worktree_path=path,
        )
        write_json(task_dir(root, task_id) / "pr-result.json", result)
        return result, 1
    return _result(
        task_id,
        candidate_id=candidate_id,
        status="prepared",
        reason="local_pr_ref_prepared",
        ref=ref,
        head_sha=head_sha,
        base_sha=base_sha,
        candidate_diff_sha256=candidate_sha,
        diff_sha256=diff_sha,
        worktree_path=path,
    ), 0


def _commit_pr_worktree(
    path: Path,
    task_id: str,
    candidate_id: str,
) -> subprocess.CompletedProcess[str]:
    git(path, ["switch", "--no-track", "-C", _pr_branch(task_id, candidate_id), "HEAD"])
    git(path, ["add", "-A"])
    return git(path, ["commit", "-m", f"harness pr {task_id} {candidate_id}"], check=False)


def _write_external_pr_blocked(
    root: Path,
    task_id: str,
    prepared: dict[str, Any],
    published: dict[str, Any],
) -> dict[str, Any]:
    result = {
        **prepared,
        "status": "blocked",
        "reason": str(published["reason"]),
        "external_pr": published,
    }
    write_json(task_dir(root, task_id) / "pr-result.json", result)
    return result


def check_local_pr(root: Path, task_id: str) -> tuple[dict[str, Any], int]:
    created = latest_event_payload(root, task_id, "PR_CREATED")
    if created is None:
        return _write_pr_check_missing(root, task_id), 1
    ref = str(created["ref"])
    base_sha = str(created["base_sha"])
    candidate_sha = str(created["candidate_diff_sha256"])
    candidate_id = candidate_id_from_patch_sha256(candidate_sha)
    current_head = _ref_head(root, ref)
    diff_sha = _diff_hash(root, base_sha, current_head) if current_head is not None else None
    if current_head is None or diff_sha != candidate_sha:
        return _write_pr_check_result(
            root,
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
        ), 1
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
        _record_pr_checked(root, task_id, candidate_id, candidate_sha, current_head, base_sha, ref)
    return result, 0 if passed else 1


def validate_local_pr_checked(root: Path, task_id: str, candidate_sha: str) -> dict[str, Any]:
    created = latest_event_payload(root, task_id, "PR_CREATED")
    if created is None:
        if post_review_gate_passed_for_candidate(root, task_id, candidate_sha):
            return {
                "status": "blocked",
                "reason": "pr_not_created",
            }
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


def validate_local_pr_created(root: Path, task_id: str, result: dict[str, Any]) -> bool:
    if result.get("task_id") != task_id or result.get("status") != "created":
        return False
    ref = result.get("ref")
    head_sha = result.get("head_sha")
    base_sha = result.get("base_sha")
    candidate_sha = result.get("candidate_diff_sha256")
    if not all(isinstance(item, str) and item for item in (ref, head_sha, base_sha, candidate_sha)):
        return False
    candidate_id = candidate_id_from_patch_sha256(str(candidate_sha))
    if result.get("candidate_id") != candidate_id:
        return False
    created = latest_event_payload(root, task_id, "PR_CREATED", candidate_id=candidate_id)
    if created is None:
        return False
    external = result.get("external_pr")
    url = external.get("url") if isinstance(external, dict) else None
    if not isinstance(url, str) or not url or url != created.get("github_pr_url"):
        return False
    current_head = _ref_head(root, str(ref))
    diff_sha = _diff_hash(root, str(base_sha), current_head) if current_head is not None else None
    return (
        created.get("ref") == ref
        and created.get("pr_head_sha") == head_sha
        and created.get("base_sha") == base_sha
        and created.get("candidate_diff_sha256") == candidate_sha
        and current_head == head_sha
        and diff_sha == candidate_sha
    )


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
    external_pr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
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
    if external_pr is not None:
        result["external_pr"] = external_pr
    return result


def _write_pr_result(root: Path, task_id: str, **kwargs: Any) -> dict[str, Any]:
    result = _result(task_id, **kwargs)
    write_json(task_dir(root, task_id) / "pr-result.json", result)
    return result


def _write_pr_check_missing(root: Path, task_id: str) -> dict[str, Any]:
    result = {
        "task_id": task_id,
        "status": "blocked",
        "reason": "pr_not_created",
        "ref": None,
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "pr-check-result.json", result)
    return result


def _write_pr_check_result(root: Path, task_id: str, **kwargs: Any) -> dict[str, Any]:
    result = _check_result(task_id, **kwargs)
    write_json(task_dir(root, task_id) / "pr-check-result.json", result)
    return result


def _record_pr_created(
    root: Path,
    task_id: str,
    candidate_id: str,
    candidate_sha: str,
    head_sha: str,
    verify_result: dict[str, Any],
    ref: str,
    external_pr: dict[str, Any],
) -> None:
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
            "github_pr_url": external_pr.get("url"),
            "github_pr_number": external_pr.get("number"),
            "github_repository": external_pr.get("repository"),
            "remote_branch": external_pr.get("head_branch"),
        },
        candidate_id=candidate_id,
    )


def _publish_external_pr(
    root: Path,
    path: Path,
    task_id: str,
    candidate_id: str,
    candidate_sha: str,
) -> dict[str, Any]:
    context = _external_pr_context(root, task_id, candidate_id)
    remote = str(context["remote"])
    base_branch = str(context["base_branch"])
    head_branch = str(context["head_branch"])
    pushed = git(path, ["push", "-u", remote, f"HEAD:refs/heads/{head_branch}"], check=False)
    if pushed.returncode != 0:
        return _external_failure(
            "remote_pr_branch_push_failed",
            remote=remote,
            base_branch=base_branch,
            head_branch=head_branch,
            detail=pushed.stderr.strip() or pushed.stdout.strip(),
        )
    repository = _github_repository(root, remote)
    if repository is None:
        return _external_failure(
            "github_repository_unresolved",
            remote=remote,
            base_branch=base_branch,
            head_branch=head_branch,
            detail="set HARNESS_GITHUB_REPOSITORY or use a GitHub origin remote",
        )
    return _create_or_reuse_github_pr(
        root,
        task_id=task_id,
        candidate_id=candidate_id,
        candidate_sha=candidate_sha,
        repository=repository,
        remote=remote,
        base_branch=base_branch,
        head_branch=head_branch,
    )


def _external_pr_context(root: Path, task_id: str, candidate_id: str) -> dict[str, str]:
    policy = load_policy(root)
    remote, base_branch, _ = integration_target(policy)
    return {
        "remote": remote,
        "base_branch": base_branch,
        "head_branch": _pr_branch(task_id, candidate_id),
    }


def _create_or_reuse_github_pr(
    root: Path,
    *,
    task_id: str,
    candidate_id: str,
    candidate_sha: str,
    repository: str,
    remote: str,
    base_branch: str,
    head_branch: str,
) -> dict[str, Any]:
    existing = _gh_pr_view(root, repository, head_branch)
    if existing is not None:
        return _external_created(
            existing,
            repository=repository,
            remote=remote,
            base_branch=base_branch,
            head_branch=head_branch,
            candidate_sha=candidate_sha,
            reused=True,
        )
    title = f"[harness] {task_id} {candidate_id}"
    body = _github_pr_body(task_id, candidate_id, candidate_sha)
    created = _gh_pr_create(root, repository, base_branch, head_branch, title, body)
    if created["status"] != "created":
        return _external_failure(
            str(created["reason"]),
            remote=remote,
            base_branch=base_branch,
            head_branch=head_branch,
            repository=repository,
            detail=str(created.get("detail") or ""),
        )
    viewed = _gh_pr_view(root, repository, head_branch)
    pr = viewed or created
    return _external_created(
        pr,
        repository=repository,
        remote=remote,
        base_branch=base_branch,
        head_branch=head_branch,
        candidate_sha=candidate_sha,
        reused=False,
    )


def _github_pr_body(task_id: str, candidate_id: str, candidate_sha: str) -> str:
    return (
        f"Task: `{task_id}`\n\n"
        f"Candidate: `{candidate_id}`\n\n"
        f"Candidate diff: `{candidate_sha}`\n\n"
        "Created by `harness pr create`."
    )


def _external_created(
    pr: dict[str, Any],
    *,
    repository: str,
    remote: str,
    base_branch: str,
    head_branch: str,
    candidate_sha: str,
    reused: bool,
) -> dict[str, Any]:
    return {
        "status": "created",
        "reason": "ok",
        "url": pr.get("url"),
        "number": pr.get("number"),
        "repository": repository,
        "remote": remote,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "candidate_diff_sha256": candidate_sha,
        "reused": reused,
    }


def _external_failure(
    reason: str,
    *,
    remote: str,
    base_branch: str,
    head_branch: str,
    detail: str,
    repository: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "blocked",
        "reason": reason,
        "remote": remote,
        "base_branch": base_branch,
        "head_branch": head_branch,
        "repository": repository,
        "detail": detail,
    }


def _github_repository(root: Path, remote: str) -> str | None:
    configured = os.environ.get("HARNESS_GITHUB_REPOSITORY")
    if configured:
        return configured
    configured = _git_config(root, "harness.githubRepository")
    if configured:
        return configured
    completed = git(root, ["remote", "get-url", remote], check=False)
    if completed.returncode != 0:
        return None
    return _parse_github_repository(completed.stdout.strip())


def _parse_github_repository(value: str) -> str | None:
    patterns = (
        r"^git@github\.com:([^/]+/[^/]+?)(?:\.git)?$",
        r"^https://github\.com/([^/]+/[^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/([^/]+/[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            return match.group(1)
    return None


def _gh_pr_view(root: Path, repository: str, head_branch: str) -> dict[str, Any] | None:
    completed = _gh(
        root,
        [
            "pr",
            "view",
            "--repo",
            repository,
            "--head",
            head_branch,
            "--json",
            "number,url,state,isDraft,headRefName,baseRefName",
        ],
    )
    if completed.returncode != 0:
        return None
    try:
        data = json_loads(completed.stdout)
    except ValueError:
        return None
    return {
        "number": data.get("number"),
        "url": data.get("url"),
        "state": data.get("state"),
        "is_draft": data.get("isDraft"),
        "head_branch": data.get("headRefName"),
        "base_branch": data.get("baseRefName"),
    }


def _gh_pr_create(
    root: Path,
    repository: str,
    base_branch: str,
    head_branch: str,
    title: str,
    body: str,
) -> dict[str, Any]:
    completed = _gh(
        root,
        [
            "pr",
            "create",
            "--repo",
            repository,
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body",
            body,
            "--draft",
        ],
    )
    if completed.returncode != 0:
        return {
            "status": "blocked",
            "reason": "github_pr_create_failed",
            "detail": completed.stderr.strip() or completed.stdout.strip(),
        }
    url = _first_url(completed.stdout)
    return {
        "status": "created",
        "reason": "ok",
        "url": url,
        "number": _pr_number(url),
    }


def _gh(root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    configured = os.environ.get("HARNESS_GH_BIN") or _git_config(root, "harness.ghBin")
    return subprocess.run(
        [configured or "gh", *args],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def _git_config(root: Path, key: str) -> str | None:
    completed = git(root, ["config", "--get", key], check=False)
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def json_loads(value: str) -> dict[str, Any]:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def _first_url(value: str) -> str | None:
    match = re.search(r"https://\S+", value)
    return match.group(0) if match else None


def _pr_number(url: str | None) -> int | None:
    if not url:
        return None
    match = re.search(r"/pull/(\d+)(?:\D*)?$", url)
    return int(match.group(1)) if match else None


def _record_pr_checked(
    root: Path,
    task_id: str,
    candidate_id: str,
    candidate_sha: str,
    current_head: str,
    base_sha: str,
    ref: str,
) -> None:
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


def _pr_ref(task_id: str, candidate_id: str) -> str:
    return f"refs/harness/pr/{_ref_component(task_id)}/{_ref_component(candidate_id)}"


def _pr_branch(task_id: str, candidate_id: str) -> str:
    return f"agent/{_ref_component(task_id)}/integrator/pr-{_ref_component(candidate_id)}"


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
