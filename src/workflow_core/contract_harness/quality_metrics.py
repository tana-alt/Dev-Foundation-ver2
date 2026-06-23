from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

REVIEW_FUNCTION_LINES = 60
HARD_FUNCTION_LINES = 220
REVIEW_NESTING_DEPTH = 4
HARD_NESTING_DEPTH = 8
REVIEW_CYCLOMATIC_COMPLEXITY = 10
HARD_CYCLOMATIC_COMPLEXITY = 40

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


def evaluate_quality(root: Path, paths: list[str]) -> dict[str, Any]:
    hard_failures: list[dict[str, Any]] = []
    review_flags: list[dict[str, Any]] = []
    checked = 0
    for rel_path in _expanded_paths(root, paths):
        path = root / rel_path
        if path.suffix != ".py" or not path.is_file():
            continue
        checked += 1
        _inspect_python_file(path, rel_path, hard_failures, review_flags)
    return quality_payload(checked, hard_failures, review_flags)


def empty_quality() -> dict[str, Any]:
    return quality_payload(0, [], [])


def quality_payload(
    checked_files: int,
    hard_failures: list[dict[str, Any]],
    review_flags: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": status_from_findings(hard_failures, review_flags),
        "checked_files": checked_files,
        "hard_failures": hard_failures,
        "review_flags": review_flags,
        "policy_anchor": {
            "machine": "Hard gate covers objective breakage only.",
            "reviewer": "Readability and extension signals are reviewed semantically.",
        },
    }


def status_from_findings(hard_failures: list[dict[str, Any]], review_flags: object) -> str:
    if hard_failures:
        return "fail"
    return "review_required" if review_flags else "pass"


def _inspect_python_file(
    path: Path,
    rel_path: str,
    hard_failures: list[dict[str, Any]],
    review_flags: list[dict[str, Any]],
) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        hard_failures.append(
            {
                "kind": "syntax_error",
                "path": rel_path,
                "line": exc.lineno or 0,
                "message": exc.msg,
            }
        )
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _inspect_function(rel_path, node, hard_failures, review_flags)


def _inspect_function(
    rel_path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    hard_failures: list[dict[str, Any]],
    review_flags: list[dict[str, Any]],
) -> None:
    del hard_failures
    length = (node.end_lineno or node.lineno) - node.lineno + 1
    if length > REVIEW_FUNCTION_LINES:
        review_flags.append(_function_issue("function_length_review", rel_path, node, length))
    depth = _nesting_depth(node)
    if depth > REVIEW_NESTING_DEPTH:
        review_flags.append(_function_issue("nesting_review", rel_path, node, depth))
    complexity = _cyclomatic_complexity(node)
    if complexity > REVIEW_CYCLOMATIC_COMPLEXITY:
        review_flags.append(
            _function_issue("cyclomatic_complexity_review", rel_path, node, complexity)
        )


def _expanded_paths(root: Path, paths: list[str]) -> list[str]:
    expanded: set[str] = set()
    for rel_path in paths:
        path = root / rel_path
        if path.is_dir():
            expanded.update(
                str(child.relative_to(root)).replace("\\", "/")
                for child in path.rglob("*")
                if child.is_file()
            )
        else:
            expanded.add(rel_path)
    return sorted(expanded)


def _function_issue(
    kind: str,
    rel_path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    observed: int,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": rel_path,
        "line": node.lineno,
        "symbol": node.name,
        "observed": observed,
    }


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    worst = depth
    for child in ast.iter_child_nodes(node):
        next_depth = depth + 1 if isinstance(child, _NESTING_NODES) else depth
        worst = max(worst, _nesting_depth(child, next_depth))
    return worst


def _cyclomatic_complexity(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            ast.If
            | ast.For
            | ast.AsyncFor
            | ast.While
            | ast.ExceptHandler
            | ast.Assert
            | ast.IfExp
            | ast.Match,
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += max(len(child.values) - 1, 0)
        elif isinstance(child, ast.comprehension):
            complexity += 1 + len(child.ifs)
    return complexity
