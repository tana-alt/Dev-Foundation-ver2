"""Code-quality gate beyond types: readability and complexity budgets.

Ruff's C901 bounds cyclomatic complexity; this test bounds what C901 does not:
function length and statement nesting depth, both strong readability signals.
Legacy heavy-contract checkers are grandfathered explicitly -- new code must
meet the budget, and shrinking a legacy file below budget removes its
exemption permanently (the lists only shrink).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MAX_FUNCTION_LINES = 60
MAX_NESTING_DEPTH = 4

# Pre-budget files allowed to exceed the limits. Do not add entries.
GRANDFATHERED = {
    "scripts/agent_operational_checks.py",
    "scripts/check-lane-map.py",
}

_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)


def checked_files() -> list[Path]:
    files = [
        *(ROOT / "src").rglob("*.py"),
        *(ROOT / "scripts").glob("*.py"),
        *(ROOT / "app").rglob("*.py"),
    ]
    return sorted(path for path in files if "__pycache__" not in path.parts)


def nesting_depth(node: ast.AST, depth: int = 0) -> int:
    worst = depth
    for child in ast.iter_child_nodes(node):
        next_depth = depth + 1 if isinstance(child, _NESTING_NODES) else depth
        worst = max(worst, nesting_depth(child, next_depth))
    return worst


def violations_in(path: Path) -> list[str]:
    found: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        rel = path.relative_to(ROOT)
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > MAX_FUNCTION_LINES:
            found.append(
                f"{rel}:{node.lineno} {node.name} is {length} lines "
                f"(max {MAX_FUNCTION_LINES}); extract helpers"
            )
        depth = nesting_depth(node)
        if depth > MAX_NESTING_DEPTH:
            found.append(
                f"{rel}:{node.lineno} {node.name} nests {depth} deep "
                f"(max {MAX_NESTING_DEPTH}); flatten with early returns"
            )
    return found


def test_functions_stay_readable() -> None:
    violations: list[str] = []
    for path in checked_files():
        if str(path.relative_to(ROOT)) in GRANDFATHERED:
            continue
        violations.extend(violations_in(path))
    assert not violations, "\n" + "\n".join(violations)


def test_grandfathered_files_still_exist() -> None:
    """A removed or renamed legacy file must also leave the exemption list."""
    for rel in sorted(GRANDFATHERED):
        assert (ROOT / rel).is_file(), f"stale grandfather entry: {rel}"
