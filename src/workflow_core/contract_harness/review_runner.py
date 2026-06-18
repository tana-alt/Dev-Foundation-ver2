from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.command_runner import (
    command_failure_summary,
    command_result_artifact,
    env_timeout_s,
    run_command,
)
from workflow_core.contract_harness.config import review_settings
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.review import run_profile, stale_or_missing
from workflow_core.contract_harness.runtime_paths import task_dir


class ReviewRunnerError(RuntimeError):
    def __init__(self, reviewer_id: str, result: dict[str, Any]) -> None:
        self.reviewer_id = reviewer_id
        self.result = result
        super().__init__(f"reviewer_failed:{reviewer_id}: {command_failure_summary(result)}")


def run_missing_reviewers(
    root: Path,
    task_id: str,
    run_one: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    settings = review_settings(root)
    if not settings["background_auto_run"]:
        return []
    results: list[dict[str, Any]] = []
    for reviewer_id in stale_or_missing(root, task_id):
        results.append(run_one(reviewer_id))
    return results


def run_reviewer_subprocess(
    root: Path,
    task_id: str,
    reviewer_id: str,
    harness_bin: Path,
) -> dict[str, Any]:
    result = run_command(
        [str(harness_bin), "review", task_id, "--run", reviewer_id],
        cwd=root,
        timeout_s=env_timeout_s("FOUNDATION_GATE_TIMEOUT_S", 900),
        env={**os.environ, "HARNESS_ROLE": "reviewer"},
    )
    artifact = _write_run_result(root, task_id, reviewer_id, result, mode="subprocess")
    if int(result["exit_code"]) != 0:
        raise ReviewRunnerError(reviewer_id, artifact)
    return artifact


def run_reviewer_in_process(root: Path, task_id: str, reviewer_id: str) -> dict[str, Any]:
    start = time.monotonic()
    try:
        verdict = run_profile(root, task_id, reviewer_id)
    except Exception as exc:
        result = {
            "status": "fail",
            "reason": "exception",
            "command": "workflow_core.contract_harness.review.run_profile",
            "command_display": "review.run_profile",
            "cwd": str(root),
            "exit_code": 1,
            "duration_ms": int((time.monotonic() - start) * 1000),
            "timeout_s": None,
            "timed_out": False,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }
        artifact = _write_run_result(root, task_id, reviewer_id, result, mode="in_process")
        raise ReviewRunnerError(reviewer_id, artifact) from exc
    result = {
        "status": "pass",
        "reason": "ok",
        "command": "workflow_core.contract_harness.review.run_profile",
        "command_display": "review.run_profile",
        "cwd": str(root),
        "exit_code": 0,
        "duration_ms": int((time.monotonic() - start) * 1000),
        "timeout_s": None,
        "timed_out": False,
        "stdout_tail": "",
        "stderr_tail": "",
        "verdict": verdict,
    }
    return _write_run_result(root, task_id, reviewer_id, result, mode="in_process")


def _write_run_result(
    root: Path,
    task_id: str,
    reviewer_id: str,
    result: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    artifact = {
        "task_id": task_id,
        "reviewer_id": reviewer_id,
        "mode": mode,
        **command_result_artifact(result),
        "written_by": "harness",
    }
    write_json(task_dir(root, task_id) / "review-runs" / f"{reviewer_id}.json", artifact)
    return artifact
