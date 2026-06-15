"""Functional-correctness gate runner (Plan-N0002 R4).

Performance comparison presupposes a functionally correct candidate; check
mechanizes that precondition: run the configured verification commands inside
a worktree, reduce them with AND, and land structured results in the run
store so gate can read them back.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from workflow_core.contracts import StrictModel
from workflow_core.runstore import RunStore

_FAILURE_TAIL_LINES = 10


class CheckResult(StrictModel):
    name: str
    status: Literal["pass", "fail"]
    duration_s: float
    command: str
    failures: list[str]


class CheckReport(StrictModel):
    worktree: str
    results: list[CheckResult]
    overall: Literal["pass", "fail"]

    def to_payload(self) -> dict[str, object]:
        """R4 output shape: results keyed by check name, failures only on fail."""
        results: dict[str, object] = {}
        for result in self.results:
            entry: dict[str, object] = {
                "status": result.status,
                "duration_s": result.duration_s,
                "command": result.command,
            }
            if result.failures:
                entry["failures"] = result.failures
            results[result.name] = entry
        return {
            "tool": "check",
            "worktree": self.worktree,
            "results": results,
            "overall": self.overall,
        }


def _run_one(name: str, command: str, *, cwd: Path, timeout: float) -> CheckResult:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            shlex.split(command), cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        duration = round(time.perf_counter() - started, 4)
        failure = f"{type(exc).__name__}: {exc}"
        return CheckResult(
            name=name, status="fail", duration_s=duration, command=command, failures=[failure]
        )
    duration = round(time.perf_counter() - started, 4)
    if proc.returncode == 0:
        return CheckResult(
            name=name, status="pass", duration_s=duration, command=command, failures=[]
        )
    tail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-_FAILURE_TAIL_LINES:]
    return CheckResult(
        name=name,
        status="fail",
        duration_s=duration,
        command=command,
        failures=[f"exit {proc.returncode}", *tail],
    )


def run_checks(
    commands: Sequence[tuple[str, str]], *, cwd: Path, timeout: float = 1800.0
) -> CheckReport:
    """Run (name, command) pairs in order; overall is the AND of all statuses."""
    results = [_run_one(name, command, cwd=cwd, timeout=timeout) for name, command in commands]
    passed = all(result.status == "pass" for result in results)
    return CheckReport(worktree=str(cwd), results=results, overall="pass" if passed else "fail")


def record_report(store: RunStore, run_id: str, report: CheckReport) -> None:
    for result in report.results:
        store.record_check(
            run_id,
            result.name,
            status=result.status,
            duration_s=result.duration_s,
            command=result.command,
            failures=result.failures,
        )
