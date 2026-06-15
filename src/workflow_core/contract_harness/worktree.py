from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.contract import load_contract
from workflow_core.contract_harness.gitutil import common_dir, git
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.policy import integration_target, load_policy
from workflow_core.contract_harness.runtime_paths import runtime_root, task_dir
from workflow_core.contract_harness.snapshot import (
    candidate_diff_hash,
    changed_repo_paths,
    snapshot_diff,
)

_MARKER = ".harness-worktree.json"


def create_worktree(
    root: Path,
    task_id: str,
    *,
    kind: str,
    reviewer_id: str | None = None,
) -> dict[str, Any]:
    if kind not in {"writer", "reviewer", "integrator"}:
        raise ValueError("worktree kind must be writer, reviewer, or integrator")
    if kind == "reviewer" and not reviewer_id:
        raise ValueError("reviewer worktree requires reviewer_id")
    base_ref = _base_ref(root, task_id, kind)
    path = _worktree_path(root, task_id, kind, reviewer_id)
    _ensure_worktree(root, path, base_ref, task_id=task_id, kind=kind, reviewer_id=reviewer_id)
    if kind == "reviewer":
        _apply_candidate(root, task_id, path)
    result = {
        "task_id": task_id,
        "kind": kind,
        "reviewer_id": reviewer_id,
        "path": str(path),
        "base_ref": base_ref,
        "state": "active",
        "head_sha": git(path, ["rev-parse", "HEAD"]).stdout.strip(),
    }
    write_json(task_dir(root, task_id) / f"{kind}-worktree.json", result)
    return result


def integrator_path(root: Path, task_id: str) -> Path:
    return _worktree_path(root, task_id, "integrator", None)


def seal_candidate_workspace(
    root: Path,
    task_id: str,
    candidate_diff_sha256: str,
) -> dict[str, Any]:
    marker = root / _MARKER
    if marker.is_file():
        _validate_marker(root, marker, task_id=task_id, kind="writer", reviewer_id=None)
        data = read_json(marker)
        data["state"] = "sealed_for_review"
        data["candidate_diff_sha256"] = candidate_diff_sha256
        write_json(marker, data)
        record = _candidate_workspace_record(
            root,
            task_id,
            kind="writer",
            state="sealed_for_review",
            candidate_diff_sha256=candidate_diff_sha256,
        )
    else:
        record = _candidate_workspace_record(
            root,
            task_id,
            kind="canonical",
            state="submitted",
            candidate_diff_sha256=candidate_diff_sha256,
        )
    write_json(task_dir(root, task_id) / "candidate-workspace.json", record)
    return record


def resolve_candidate_workspace(
    root: Path,
    task_id: str,
    *,
    expected_hash: str | None,
) -> dict[str, Any]:
    record = _submitted_candidate_workspace(root, task_id)
    path = Path(str(record["path"]))
    if not path.is_dir():
        raise ValueError("candidate workspace is missing")
    if common_dir(path).resolve() != common_dir(root).resolve():
        raise ValueError("candidate workspace does not belong to this repository")
    if expected_hash is not None and workspace_candidate_hash(path, task_id) != expected_hash:
        raise ValueError("candidate workspace hash mismatch")
    return {**record, "path": str(path)}


def workspace_candidate_hash(root: Path, task_id: str) -> str:
    lock = load_contract(root, task_id)
    paths = changed_repo_paths(root, task_id=task_id)
    diff_text = snapshot_diff(root, str(lock["prepared_base_sha"]), paths)
    return candidate_diff_hash(diff_text)


def _base_ref(root: Path, task_id: str, kind: str) -> str:
    if kind in {"writer", "reviewer"}:
        return str(load_contract(root, task_id)["prepared_base_sha"])
    policy = load_policy(root)
    remote, branch, _ = integration_target(policy)
    git(root, ["fetch", remote, branch])
    return f"refs/remotes/{remote}/{branch}"


def _worktree_path(root: Path, task_id: str, kind: str, reviewer_id: str | None) -> Path:
    base = runtime_root(root) / "worktrees" / task_id
    if kind == "reviewer":
        assert reviewer_id is not None
        return base / "reviewers" / reviewer_id
    return base / kind


def _ensure_worktree(
    root: Path,
    path: Path,
    base_ref: str,
    *,
    task_id: str,
    kind: str,
    reviewer_id: str | None,
) -> None:
    if path.exists():
        if not (path / ".git").exists():
            raise ValueError(f"refusing to reuse non-worktree path: {path}")
        migration = _validate_existing_worktree(
            root,
            path,
            task_id=task_id,
            kind=kind,
            reviewer_id=reviewer_id,
        )
        _write_worktree_exclude(path)
        _refuse_dirty_destructive_reuse(path)
        git(path, ["checkout", "--detach", base_ref])
        git(path, ["reset", "--hard", base_ref])
        git(path, ["clean", "-fd"])
        _write_marker(
            root,
            path,
            base_ref,
            task_id=task_id,
            kind=kind,
            reviewer_id=reviewer_id,
            migration=migration,
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    git(root, ["worktree", "add", "--detach", str(path), base_ref])
    _write_worktree_exclude(path)
    _write_marker(
        root,
        path,
        base_ref,
        task_id=task_id,
        kind=kind,
        reviewer_id=reviewer_id,
        migration=None,
    )


def _validate_existing_worktree(
    root: Path,
    path: Path,
    *,
    task_id: str,
    kind: str,
    reviewer_id: str | None,
) -> str | None:
    marker = path / _MARKER
    if marker.is_file():
        _validate_marker(root, marker, task_id=task_id, kind=kind, reviewer_id=reviewer_id)
        return None
    _validate_unmarked_legacy_worktree(root, path)
    return "legacy-clean-worktree"


def _validate_marker(
    root: Path,
    marker: Path,
    *,
    task_id: str,
    kind: str,
    reviewer_id: str | None,
) -> None:
    data = read_json(marker)
    expected_common = str(common_dir(root).resolve())
    if data.get("source_repo_common_dir") != expected_common:
        raise ValueError(f"refusing to reuse worktree with foreign marker: {marker.parent}")
    expected = {"task_id": task_id, "kind": kind, "reviewer_id": reviewer_id}
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f"refusing to reuse harness worktree with mismatched marker: {key}")


def _validate_unmarked_legacy_worktree(root: Path, path: Path) -> None:
    if common_dir(path).resolve() != common_dir(root).resolve():
        raise ValueError(f"refusing to reuse foreign unmarked harness worktree: {path}")
    runtime_worktrees = (runtime_root(root) / "worktrees").resolve()
    try:
        path.resolve().relative_to(runtime_worktrees)
    except ValueError as exc:
        raise ValueError(
            f"refusing to reuse unmarked worktree outside harness runtime: {path}"
        ) from exc
    status = git(path, ["status", "--porcelain=v1"]).stdout.strip()
    if status:
        raise ValueError(f"unmarked harness worktree is dirty; refusing destructive reuse: {path}")


def _write_marker(
    root: Path,
    path: Path,
    base_ref: str,
    *,
    task_id: str,
    kind: str,
    reviewer_id: str | None,
    migration: str | None,
) -> None:
    data = {
        "task_id": task_id,
        "kind": kind,
        "reviewer_id": reviewer_id,
        "base_ref": base_ref,
        "source_repo_common_dir": str(common_dir(root).resolve()),
        "migration": migration or "created",
        "state": "active",
        "written_by": "harness",
    }
    write_json(path / _MARKER, data)


def _write_worktree_exclude(path: Path) -> None:
    git_dir = Path(git(path, ["rev-parse", "--git-dir"]).stdout.strip())
    if not git_dir.is_absolute():
        git_dir = path / git_dir
    for exclude in (git_dir / "info" / "exclude", common_dir(path) / "info" / "exclude"):
        _append_exclude_patterns(exclude)


def _append_exclude_patterns(exclude: Path) -> None:
    exclude.parent.mkdir(parents=True, exist_ok=True)
    if not exclude.is_file():
        exclude.write_text("", encoding="utf-8")
    lines = exclude.read_text(encoding="utf-8").splitlines()
    additions = [".harness-worktree.json", "artifact/"]
    changed = False
    for item in additions:
        if item not in lines:
            lines.append(item)
            changed = True
    if changed:
        exclude.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _refuse_dirty_destructive_reuse(path: Path) -> None:
    status = git(path, ["status", "--porcelain=v1"]).stdout.strip()
    if status:
        raise ValueError(f"harness worktree is dirty; refusing destructive reuse: {path}")


def _submitted_candidate_workspace(root: Path, task_id: str) -> dict[str, Any]:
    submission = task_dir(root, task_id) / "submission.json"
    if submission.is_file():
        data = read_json(submission)
        workspace = data.get("candidate_workspace")
        if isinstance(workspace, dict) and isinstance(workspace.get("path"), str):
            return workspace
    return _candidate_workspace_record(
        root,
        task_id,
        kind="canonical",
        state="working_tree",
        candidate_diff_sha256=None,
    )


def _candidate_workspace_record(
    root: Path,
    task_id: str,
    *,
    kind: str,
    state: str,
    candidate_diff_sha256: str | None,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "kind": kind,
        "state": state,
        "path": str(root),
        "candidate_diff_sha256": candidate_diff_sha256,
        "head_sha": git(root, ["rev-parse", "HEAD"]).stdout.strip(),
    }


def _apply_candidate(root: Path, task_id: str, path: Path) -> None:
    candidate = task_dir(root, task_id) / "candidate.diff"
    completed = git(
        path,
        ["apply", "--whitespace=nowarn", str(candidate)],
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "candidate apply failed")
    verify_result = read_json(task_dir(root, task_id) / "verify-result.json")
    (task_dir(root, task_id) / "reviews").mkdir(parents=True, exist_ok=True)
    write_json(
        task_dir(root, task_id) / "reviews" / "worktree-candidate.json",
        {
            "task_id": task_id,
            "candidate_diff_sha256": verify_result.get("candidate_diff_sha256"),
            "path": str(path),
        },
    )
