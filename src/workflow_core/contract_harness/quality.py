from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_core.contract_harness.hashing import file_hash
from workflow_core.contract_harness.jsonio import read_json, write_json
from workflow_core.contract_harness.quality_metrics import (
    HARD_CYCLOMATIC_COMPLEXITY,
    HARD_FUNCTION_LINES,
    HARD_NESTING_DEPTH,
    REVIEW_CYCLOMATIC_COMPLEXITY,
    REVIEW_FUNCTION_LINES,
    REVIEW_NESTING_DEPTH,
    empty_quality,
    evaluate_quality,
)
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.tool_candidates import (
    TOOL_PROBE_TIMEOUT_S,
    empty_tool_candidates,
    evaluate_tool_candidates,
)

__all__ = [
    "HARD_CYCLOMATIC_COMPLEXITY",
    "HARD_FUNCTION_LINES",
    "HARD_NESTING_DEPTH",
    "REVIEW_CYCLOMATIC_COMPLEXITY",
    "REVIEW_FUNCTION_LINES",
    "REVIEW_NESTING_DEPTH",
    "TOOL_PROBE_TIMEOUT_S",
    "evaluate_quality",
    "evaluate_tool_candidates",
    "quality_gate_verifier",
    "quality_result",
    "quality_result_hash",
    "tool_candidate_gate_verifier",
    "tool_candidates_hash",
    "tool_candidates_result",
    "write_quality_artifacts",
]


def write_quality_artifacts(
    root: Path,
    task_id: str,
    paths: list[str],
    verifier_plan: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = evaluate_quality(root, paths)
    tool_candidates = evaluate_tool_candidates(root, task_id, paths, verifier_plan)
    runtime = task_dir(root, task_id)
    write_json(runtime / "quality-result.json", quality)
    write_json(runtime / "tool-candidates.json", tool_candidates)
    return quality, tool_candidates


def quality_result_hash(root: Path, task_id: str) -> str | None:
    path = task_dir(root, task_id) / "quality-result.json"
    return file_hash(path) if path.is_file() else None


def tool_candidates_hash(root: Path, task_id: str) -> str | None:
    path = task_dir(root, task_id) / "tool-candidates.json"
    return file_hash(path) if path.is_file() else None


def quality_result(root: Path, task_id: str) -> dict[str, Any]:
    path = task_dir(root, task_id) / "quality-result.json"
    if path.is_file():
        return read_json(path)
    return empty_quality()


def tool_candidates_result(root: Path, task_id: str) -> dict[str, Any]:
    path = task_dir(root, task_id) / "tool-candidates.json"
    if path.is_file():
        return read_json(path)
    return empty_tool_candidates()


def quality_gate_verifier(result: dict[str, Any]) -> dict[str, Any]:
    return _synthetic_verifier("quality-hard-gate", result)


def tool_candidate_gate_verifier(result: dict[str, Any]) -> dict[str, Any]:
    return _synthetic_verifier("tool-candidate-durable-gate", result)


def _synthetic_verifier(verifier_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": verifier_id,
        "status": "fail" if result.get("status") == "fail" else "pass",
        "exit_code": 1 if result.get("status") == "fail" else 0,
        "duration_ms": 0,
    }
