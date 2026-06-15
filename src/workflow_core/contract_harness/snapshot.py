from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.gitutil import git, status_paths
from workflow_core.contract_harness.hashing import sha256_text
from workflow_core.contract_harness.paths import PathPolicy, relative_to_repo
from workflow_core.contract_harness.runtime_paths import runtime_root

PROPOSAL_PATTERNS = [".harness/proposals/**"]
IGNORED_RUNTIME_PATHS = {".harness-worktree.json"}


def changed_repo_paths(root: Path, *, task_id: str | None = None) -> list[str]:
    runtime_rel = relative_to_repo(root, runtime_root(root))
    paths = status_paths(root)
    if runtime_rel is None:
        filtered = paths
    else:
        filtered = [path for path in paths if not path.startswith(runtime_rel.rstrip("/") + "/")]
    if task_id is None:
        return filtered
    return [
        path
        for path in filtered
        if path not in IGNORED_RUNTIME_PATHS
        and path != "artifact/"
        and not path.startswith("artifact/")
    ]


def scope_violations(paths: list[str], contract: dict[str, Any]) -> list[dict[str, str]]:
    scope = contract["scope_contract"]
    allowed = PathPolicy([*scope["allowed_paths"], *PROPOSAL_PATTERNS])
    forbidden = PathPolicy(scope["forbidden_paths"])
    violations: list[dict[str, str]] = []
    for path in paths:
        reason = _violation_reason(path, allowed, forbidden)
        if reason:
            violations.append({"path": path, "reason": reason})
    return violations


def snapshot_diff(root: Path, base_sha: str, paths: list[str]) -> str:
    with tempfile.TemporaryDirectory(prefix="harness-index-") as tmp:
        index = str(Path(tmp) / "index")
        env = {"GIT_INDEX_FILE": index}
        git(root, ["read-tree", base_sha], env=env)
        for path in sorted(paths):
            _stage_path(root, env, path)
        return git(
            root,
            [
                "-c",
                "core.autocrlf=false",
                "-c",
                "diff.noprefix=false",
                "-c",
                "diff.renames=false",
                "diff",
                "--cached",
                "--binary",
                "--full-index",
                base_sha,
            ],
            env=env,
        ).stdout


def candidate_diff_hash(diff_text: str) -> str:
    return sha256_text(diff_text)


def diff_index(diff_text: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = _diff_file(line)
            files.append(current)
            continue
        if current is None:
            continue
        _update_diff_file(current, line)
    return {
        "file_count": len(files),
        "changed_files": [str(item["path"]) for item in files],
        "total_additions": sum(int(item["additions"]) for item in files),
        "total_deletions": sum(int(item["deletions"]) for item in files),
        "total_hunks": sum(int(item["hunks"]) for item in files),
        "files": files,
    }


def _diff_file(line: str) -> dict[str, Any]:
    return {
        "path": _diff_path(line),
        "additions": 0,
        "deletions": 0,
        "hunks": 0,
        "binary": False,
    }


def _update_diff_file(current: dict[str, Any], line: str) -> None:
    if line.startswith("@@"):
        current["hunks"] = int(current["hunks"]) + 1
    elif line.startswith("Binary files "):
        current["binary"] = True
    elif line.startswith("+") and not line.startswith("+++ "):
        current["additions"] = int(current["additions"]) + 1
    elif line.startswith("-") and not line.startswith("--- "):
        current["deletions"] = int(current["deletions"]) + 1


def _diff_path(line: str) -> str:
    parts = line.split()
    if len(parts) >= 4:
        return parts[3][2:] if parts[3].startswith("b/") else parts[3]
    return ""


def _violation_reason(path: str, allowed: PathPolicy, forbidden: PathPolicy) -> str:
    if forbidden.matches(path):
        return "forbidden_path"
    if allowed.matches(path):
        return ""
    return "outside_allowed_paths"


def _stage_path(root: Path, env: dict[str, str], path: str) -> None:
    target = root / path
    if target.exists() or target.is_symlink():
        git(root, ["add", "--", path], env=env)
        return
    git(root, ["rm", "-q", "--ignore-unmatch", "--", path], env=env)
