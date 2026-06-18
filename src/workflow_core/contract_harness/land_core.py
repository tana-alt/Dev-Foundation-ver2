from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from workflow_core.contract_harness.command_runner import env_timeout_s, run_command
from workflow_core.contract_harness.contract import load_verifier_plan
from workflow_core.contract_harness.gitutil import git
from workflow_core.contract_harness.runtime_paths import task_dir
from workflow_core.contract_harness.verifier import all_passed, run_verifiers


def apply_candidate_diff(root: Path, task_id: str, path: Path) -> subprocess.CompletedProcess[str]:
    candidate = task_dir(root, task_id) / "candidate.diff"
    return git(path, ["apply", "--whitespace=nowarn", str(candidate)], check=False)


def run_machine_gate(path: Path, task_id: str) -> dict[str, Any]:
    if "FOUNDATION_GATE_TIER" not in os.environ:
        verifiers = run_verifiers(path, load_verifier_plan(path, task_id))
        passed = all_passed(verifiers)
        return {
            "status": "pass" if passed else "fail",
            "command": "harness verifiers: "
            + ", ".join(str(item.get("id", "")) for item in verifiers),
            "exit_code": 0 if passed else 1,
            "verifiers": verifiers,
        }
    tier = os.environ.get("FOUNDATION_GATE_TIER", "check-required")
    completed = run_command(
        ["make", tier],
        cwd=path,
        timeout_s=env_timeout_s("FOUNDATION_GATE_TIMEOUT_S", 900),
    )
    return {
        "status": "pass" if int(completed["exit_code"]) == 0 else "fail",
        "command": f"make {tier}",
        "exit_code": completed["exit_code"],
        "duration_ms": completed["duration_ms"],
        "timed_out": completed["timed_out"],
    }


def commit_land(path: Path, task_id: str) -> str:
    git(path, ["add", "-A"])
    git(path, ["commit", "-m", f"land {task_id}"])
    return git(path, ["rev-parse", "HEAD"]).stdout.strip()
