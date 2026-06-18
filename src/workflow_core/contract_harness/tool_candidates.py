from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.command_runner import command_failure_summary, run_command
from workflow_core.contract_harness.quality_metrics import status_from_findings

TOOL_PROBE_TIMEOUT_S = 5


def evaluate_tool_candidates(
    root: Path,
    task_id: str,
    paths: list[str],
    verifier_plan: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = [
        candidate
        for rel_path in _expanded_paths(root, paths)
        if (candidate := _candidate_for_path(root, rel_path, task_id)) is not None
    ]
    hard_failures = [
        {"path": candidate["path"], "kind": check["name"], "message": check["message"]}
        for candidate in candidates
        for check in candidate["durable_checks"]
        if check["status"] == "fail"
    ]
    review_flags = [
        {"path": candidate["path"], **flag}
        for candidate in candidates
        for flag in candidate["review_flags"]
    ]
    return {
        "status": status_from_findings(hard_failures, review_flags or candidates),
        "candidates": candidates,
        "hard_failures": hard_failures,
        "review_flags": review_flags,
        "tool_inventory": {
            "verifiers": [
                {"id": str(item.get("id", "")), "command": str(item.get("command", ""))}
                for item in verifier_plan
            ],
            "changed_tool_count": len(candidates),
        },
        "policy_anchor": {
            "machine": "Durable structure is checked mechanically.",
            "reviewer": "Semantic reuse and anti-gaming judgement stays with reviewer.",
        },
    }


def empty_tool_candidates() -> dict[str, Any]:
    return {
        "status": "pass",
        "candidates": [],
        "hard_failures": [],
        "review_flags": [],
        "tool_inventory": {"verifiers": [], "changed_tool_count": 0},
        "policy_anchor": {
            "machine": "Durable structure is checked mechanically.",
            "reviewer": "Semantic reuse and anti-gaming judgement stays with reviewer.",
        },
    }


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


def _candidate_for_path(root: Path, rel_path: str, task_id: str) -> dict[str, Any] | None:
    path = root / rel_path
    if not path.is_file():
        return None
    kind = _candidate_kind(rel_path)
    if kind is None:
        return None
    text = path.read_text(encoding="utf-8")
    return {
        "path": rel_path,
        "kind": kind,
        "durable_checks": _durable_checks(root, rel_path, kind, text),
        "review_flags": _tool_review_flags(text, task_id),
    }


def _candidate_kind(rel_path: str) -> str | None:
    parts = rel_path.split("/")
    if len(parts) == 2 and parts[0] == "scripts" and rel_path.endswith(".py"):
        return "script"
    if len(parts) == 4 and parts[:2] == [".agents", "skills"] and parts[3] == "SKILL.md":
        return "skill"
    if len(parts) >= 5 and "skills" in parts and parts[-1] == "SKILL.md":
        return "plugin_skill"
    return None


def _durable_checks(root: Path, rel_path: str, kind: str, text: str) -> list[dict[str, str]]:
    checks = [{"name": "non_empty", "status": "pass" if text.strip() else "fail"}]
    if kind == "script":
        has_entrypoint = "if __name__" in text and "main(" in text
        checks.append(
            {
                "name": "script_entrypoint",
                "status": "pass" if has_entrypoint else "fail",
                "message": "" if has_entrypoint else "script tool needs a durable entrypoint",
            }
        )
        checks.append(_script_help_probe(root, rel_path))
    return [_with_message(check) for check in checks]


def _script_help_probe(root: Path, rel_path: str) -> dict[str, str]:
    completed = run_command(
        [sys.executable, rel_path, "--help"],
        cwd=root,
        timeout_s=TOOL_PROBE_TIMEOUT_S,
    )
    message = ""
    if int(completed["exit_code"]) != 0:
        message = command_failure_summary(completed)
    return {
        "name": "script_help_probe",
        "status": "pass" if int(completed["exit_code"]) == 0 else "fail",
        "message": message,
    }


def _tool_review_flags(text: str, task_id: str) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if task_id and task_id in text:
        flags.append({"kind": "task_id_literal", "message": "tool mentions current task id"})
    if not any(token in text for token in ("argparse", "sys.argv", "HARNESS_", "{")):
        flags.append({"kind": "parameterization_review", "message": "parameterization is unclear"})
    return flags


def _with_message(check: dict[str, str]) -> dict[str, str]:
    if "message" in check:
        return check
    return {**check, "message": ""}
