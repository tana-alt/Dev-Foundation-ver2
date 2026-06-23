from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PredicateFinding:
    code: str
    check_kind: str
    requires_human_review: bool = False


FORBIDDEN_STORAGE_ROOTS = (
    "harness-runtime/",
    ".harness/state/",
    ".serena/",
    ".codex/",
    "logs/",
    "cache/",
    ".cache/",
)

_ACTIVE_DOC_FILES = {
    "AGENTS.md",
    "docs/01-agent-operating-contract.md",
    "docs/02-output-verification-contract.md",
    "docs/03-repo-boundary-and-storage-contract.md",
}
_FORBIDDEN_ACTIVE_DOC_RE = re.compile(
    r"^(docs/04-[^/]+\.md|docs/system-design\.md|"
    r"docs/architecture-principles\.md|docs/adr/|docs/design/)"
)
_SKILL_INDEX_ENTRY_RE = re.compile(r"^- `([^`]+)`$")
_EXTERNAL_WRITE_RE = re.compile(
    r"(?x)"
    r"\brequests\.(post|put|patch|delete)\s*\(|"
    r"\bhttpx\.(post|put|patch|delete)\s*\(|"
    r"\burllib\.request\.urlopen\s*\(|"
    r"\bput_object\s*\(|"
    r"\bsubprocess\.(run|Popen|call|check_call|check_output)\s*\(.*"
    r"(['\"]git['\"].*['\"]push['\"]|['\"]curl['\"]|['\"]gh['\"].*['\"]release['\"])"
)
_RUNTIME_STATE_SUFFIXES = {
    ".log",
    ".sqlite",
    ".db",
    ".session",
    ".cookie",
    ".token",
    ".secret",
}


def run_hard_block_predicates(
    root: Path,
    *,
    changed_paths: list[str],
    diff_text: str,
) -> tuple[PredicateFinding, ...]:
    added_paths = _added_paths(diff_text)
    added_lines = _added_lines(diff_text)
    findings: list[PredicateFinding] = []
    for checker in (
        _check_active_doc_expansion,
        _check_new_storage_root,
        _check_tracked_runtime_state,
        _check_broad_repo_scan_default,
        _check_unindexed_skill,
        _check_skill_compact_limit,
        _check_possible_external_write_path,
    ):
        findings.extend(checker(root, changed_paths, added_paths, added_lines, diff_text))
    return tuple(_dedupe_findings(findings))


def _check_active_doc_expansion(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del root, changed_paths
    if any(_FORBIDDEN_ACTIVE_DOC_RE.match(path) for path in added_paths):
        return [_finding("ACTIVE_DOC_EXPANSION")]
    if "AGENTS.md" in _changed_files(diff_text) and any(
        _FORBIDDEN_ACTIVE_DOC_RE.search(line) for line in added_lines
    ):
        return [_finding("ACTIVE_DOC_EXPANSION")]
    if any(
        path not in _ACTIVE_DOC_FILES and _FORBIDDEN_ACTIVE_DOC_RE.match(path)
        for path in added_paths
    ):
        return [_finding("ACTIVE_DOC_EXPANSION")]
    return []


def _check_new_storage_root(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del root, changed_paths, added_lines, diff_text
    if any(path.startswith(FORBIDDEN_STORAGE_ROOTS) for path in added_paths):
        return [_finding("NEW_STORAGE_ROOT")]
    return []


def _check_tracked_runtime_state(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del root, added_paths, added_lines, diff_text
    if any(_is_runtime_state_path(path) for path in changed_paths):
        return [_finding("TRACKED_RUNTIME_STATE")]
    return []


def _check_broad_repo_scan_default(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del root, changed_paths, added_paths, diff_text
    if any(line.strip() == "broad_repo_scan_allowed: true" for line in added_lines):
        return [_finding("BROAD_REPO_SCAN_DEFAULT_TRUE")]
    return []


def _check_unindexed_skill(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del changed_paths, added_lines, diff_text
    added_skills = sorted(_skill_name(path) for path in added_paths if _is_skill_file(path))
    missing = [skill for skill in added_skills if skill and skill not in _indexed_skills(root)]
    if missing:
        return [_finding("UNINDEXED_SKILL")]
    return []


def _check_skill_compact_limit(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del added_paths, added_lines, diff_text
    for path in changed_paths:
        if not _is_skill_file(path):
            continue
        target = root / path
        if target.is_file() and _line_count(target) > 80:
            return [_finding("SKILL_COMPACT_LIMIT_EXCEEDED")]
    return []


def _check_possible_external_write_path(
    root: Path,
    changed_paths: list[str],
    added_paths: set[str],
    added_lines: list[str],
    diff_text: str,
) -> list[PredicateFinding]:
    del root, changed_paths, added_paths, added_lines
    for path, line in _added_lines_by_path(diff_text):
        if _is_reference_only_path(path):
            continue
        if "architecture-gate: allow-external-write" in line:
            continue
        if _EXTERNAL_WRITE_RE.search(line):
            return [
                PredicateFinding(
                    "POSSIBLE_EXTERNAL_WRITE_PATH",
                    "conservative_heuristic",
                    requires_human_review=True,
                )
            ]
    return []


def _finding(code: str, check_kind: str = "deterministic") -> PredicateFinding:
    return PredicateFinding(code, check_kind)


def _dedupe_findings(findings: list[PredicateFinding]) -> list[PredicateFinding]:
    seen: set[str] = set()
    deduped: list[PredicateFinding] = []
    for finding in findings:
        if finding.code in seen:
            continue
        seen.add(finding.code)
        deduped.append(finding)
    return deduped


def _added_paths(diff_text: str) -> set[str]:
    added: set[str] = set()
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = _diff_path(line)
        elif current and line.startswith("new file mode "):
            added.add(current)
    return added


def _changed_files(diff_text: str) -> set[str]:
    return {path for line in diff_text.splitlines() if (path := _path_from_diff_header(line))}


def _path_from_diff_header(line: str) -> str | None:
    if not line.startswith("diff --git "):
        return None
    return _diff_path(line)


def _diff_path(line: str) -> str:
    parts = line.split()
    if len(parts) < 4:
        return ""
    path = parts[3]
    return path[2:] if path.startswith("b/") else path


def _added_lines(diff_text: str) -> list[str]:
    return [
        line[1:]
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++ ")
    ]


def _added_lines_by_path(diff_text: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    current = ""
    for line in diff_text.splitlines():
        if path := _path_from_diff_header(line):
            current = path
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            result.append((current, line[1:]))
    return result


def _is_reference_only_path(path: str) -> bool:
    return path.startswith("Plan/") or path.endswith(".md")


def _is_runtime_state_path(path: str) -> bool:
    name = Path(path).name
    return (
        path.startswith("harness-runtime/")
        or path == ".env"
        or name == ".env"
        or Path(path).suffix in _RUNTIME_STATE_SUFFIXES
    )


def _is_skill_file(path: str) -> bool:
    return path.startswith(".agents/skills/") and path.endswith("/SKILL.md")


def _skill_name(path: str) -> str:
    parts = path.split("/")
    return parts[2] if len(parts) >= 4 else ""


def _indexed_skills(root: Path) -> set[str]:
    index = (root / ".agents" / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    return {
        match.group(1)
        for line in index.splitlines()
        if (match := _SKILL_INDEX_ENTRY_RE.match(line))
    }


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())
