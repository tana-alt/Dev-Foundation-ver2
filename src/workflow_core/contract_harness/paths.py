from __future__ import annotations

from pathlib import Path

from pathspec import PathSpec


def repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if normalized.startswith("../") or normalized == "..":
        raise ValueError(f"path escapes repo: {path}")
    return normalized


class PathPolicy:
    def __init__(self, patterns: list[str]) -> None:
        self.patterns = [repo_path(pattern) for pattern in patterns]
        self._spec = PathSpec.from_lines("gitwildmatch", self.patterns)

    def matches(self, path: str) -> bool:
        return self._spec.match_file(repo_path(path))


def paths_from_diff(diff_text: str) -> list[str]:
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            paths.update(_diff_header_paths(line))
    return sorted(paths)


def _diff_header_paths(line: str) -> list[str]:
    parts = line.split()
    found: list[str] = []
    for token in parts[2:4]:
        if token.startswith(("a/", "b/")) and token != "/dev/null":
            found.append(token[2:])
    return found


def relative_to_repo(root: Path, path: Path) -> str | None:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return None
