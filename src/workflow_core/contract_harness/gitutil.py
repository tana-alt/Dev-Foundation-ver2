from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(
    root: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    check: bool = True,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        env=merged,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise GitError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed


def git_bytes(root: Path, args: list[str], *, timeout: int = 60) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise GitError(completed.stderr.decode("utf-8", "replace").strip())
    return completed.stdout


def repo_root(start: Path) -> Path:
    return Path(git(start, ["rev-parse", "--show-toplevel"]).stdout.strip())


def common_dir(root: Path) -> Path:
    raw = git(root, ["rev-parse", "--git-common-dir"]).stdout.strip()
    path = Path(raw)
    return path if path.is_absolute() else root / path


def head_sha(root: Path) -> str:
    return git(root, ["rev-parse", "HEAD"]).stdout.strip()


def status_paths(root: Path) -> list[str]:
    raw = git_bytes(root, ["status", "--porcelain=v1", "--untracked-files=all", "-z"])
    parts = [part for part in raw.split(b"\0") if part]
    paths: list[str] = []
    index = 0
    while index < len(parts):
        token = parts[index].decode("utf-8", "surrogateescape")
        code = token[:2]
        path = token[3:]
        paths.append(path)
        if ("R" in code or "C" in code) and index + 1 < len(parts):
            index += 1
            paths.append(parts[index].decode("utf-8", "surrogateescape"))
        index += 1
    return sorted(set(paths))
