from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.config import review_settings
from workflow_core.contract_harness.gate import gate_task
from workflow_core.contract_harness.gitutil import head_sha
from workflow_core.contract_harness.jsonio import write_json
from workflow_core.contract_harness.review import stale_or_missing
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.submission import validate_submission


def dispatch_task(
    root: Path,
    task_id: str,
    *,
    harness_bin: Path,
) -> tuple[dict[str, Any], int]:
    try:
        validate_submission(root, task_id)
    except (OSError, ValueError, KeyError) as exc:
        reason = "stale_submission" if str(exc) == "stale_submission" else str(exc)
        result = _result(task_id, status="rework_required", reason=reason)
        write_json(task_dir(root, task_id) / "integration-result.json", result)
        return result, 1
    return integrate_task(root, task_id, harness_bin=harness_bin)


def integrate_task(
    root: Path,
    task_id: str,
    *,
    harness_bin: Path,
) -> tuple[dict[str, Any], int]:
    before = head_sha(root)
    _run_missing_reviewers(root, task_id, harness_bin)
    gate_result, gate_code = gate_task(root, task_id)
    after = head_sha(root)
    status = "integrated" if gate_code == 0 else "rework_required"
    result = _from_gate(task_id, status, gate_result, before == after, root)
    write_json(task_dir(root, task_id) / "integration-result.json", result)
    return result, 0 if status == "integrated" else 1


def _run_missing_reviewers(root: Path, task_id: str, harness_bin: Path) -> None:
    settings = review_settings(root)
    if not settings["background_auto_run"]:
        return
    for reviewer_id in stale_or_missing(root, task_id):
        _run_reviewer(root, task_id, reviewer_id, harness_bin)


def _run_reviewer(root: Path, task_id: str, reviewer_id: str, harness_bin: Path) -> None:
    completed = subprocess.run(
        [str(harness_bin), "review", task_id, "--run", reviewer_id],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=int(os.environ.get("FOUNDATION_GATE_TIMEOUT_S", "900")),
        env={**os.environ, "HARNESS_ROLE": "reviewer"},
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip())


def _from_gate(
    task_id: str,
    status: str,
    gate_result: dict[str, Any],
    head_unchanged: bool,
    root: Path,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "role": "integrator",
        "status": status,
        "reason": gate_result.get("reason", "ok"),
        "candidate_diff_sha256": gate_result.get("candidate_diff_sha256"),
        "machine_evidence_sha256": gate_result.get("machine_evidence_sha256"),
        "review": gate_result.get("review", {}),
        "completion": gate_result.get("completion", {}),
        "metrics": gate_result.get("metrics", {}),
        "head_unchanged": head_unchanged,
        "integration_workspace": {
            "path": str(root),
            "head_unchanged": head_unchanged,
        },
    }


def _result(task_id: str, *, status: str, reason: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "role": "integrator",
        "status": status,
        "reason": reason,
        "review": {},
        "completion": {"status": "not_run"},
        "metrics": {},
        "head_unchanged": True,
    }
