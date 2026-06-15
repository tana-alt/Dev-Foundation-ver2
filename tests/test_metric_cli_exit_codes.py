"""Subprocess-level tests for the R6 exit-code contract of the two metric CLIs.

R6 convention:
  0  pass / budget met / no regression
  1  quality fail / budget missed / regression
  2  inconclusive (reserved, unused by these tools)
  3  tool error (no samples, bad arguments, broken command, usage error)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _env(tmp_path: Path) -> dict[str, str]:
    return {**os.environ, "FOUNDATION_REPO_ROOT": str(tmp_path), "FOUNDATION_PROJECT_ID": "t"}


def _run(script: str, args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=_env(tmp_path),
    )


# ---------------------------------------------------------------------------
# nfr_metric.py
# ---------------------------------------------------------------------------


def test_nfr_record_then_evaluate_within_budget_exit_0(tmp_path: Path) -> None:
    for i in range(10):
        r = _run("nfr_metric.py", ["record", "latency", str(50 + i)], tmp_path)
        assert r.returncode == 0, r.stderr

    r = _run(
        "nfr_metric.py",
        ["evaluate", "latency", "--threshold", "200", "--statistic", "p95"],
        tmp_path,
    )
    assert r.returncode == 0, r.stderr


def test_nfr_evaluate_budget_exceeded_exit_1(tmp_path: Path) -> None:
    for i in range(10):
        r = _run("nfr_metric.py", ["record", "latency_high", str(300 + i)], tmp_path)
        assert r.returncode == 0, r.stderr

    r = _run(
        "nfr_metric.py",
        ["evaluate", "latency_high", "--threshold", "100", "--statistic", "p95"],
        tmp_path,
    )
    assert r.returncode == 1, r.stderr


def test_nfr_evaluate_no_samples_exit_3(tmp_path: Path) -> None:
    r = _run("nfr_metric.py", ["evaluate", "nonexistent_metric", "--threshold", "100"], tmp_path)
    assert r.returncode == 3, r.stderr


def test_nfr_bogus_subcommand_exit_3(tmp_path: Path) -> None:
    r = _run("nfr_metric.py", ["bogus_subcommand"], tmp_path)
    assert r.returncode == 3, r.stderr


# ---------------------------------------------------------------------------
# bench_compare.py
# ---------------------------------------------------------------------------


def _record_bench_samples(
    label: str, value: float, count: int, benchmark: str, tmp_path: Path
) -> None:
    for _ in range(count):
        r = _run(
            "bench_compare.py",
            ["record", benchmark, str(value), "--label", label],
            tmp_path,
        )
        assert r.returncode == 0, r.stderr


def test_bench_compare_no_regression_exit_0(tmp_path: Path) -> None:
    _record_bench_samples("baseline", 100.0, 10, "speed", tmp_path)
    _record_bench_samples("candidate", 50.0, 10, "speed", tmp_path)

    r = _run("bench_compare.py", ["compare", "speed"], tmp_path)
    assert r.returncode == 0, r.stderr


def test_bench_compare_regression_exit_1(tmp_path: Path) -> None:
    _record_bench_samples("baseline", 50.0, 10, "regr", tmp_path)
    _record_bench_samples("candidate", 100.0, 10, "regr", tmp_path)

    r = _run("bench_compare.py", ["compare", "regr"], tmp_path)
    assert r.returncode == 1, r.stderr


def test_bench_compare_missing_side_exit_3(tmp_path: Path) -> None:
    # Only baseline recorded; candidate absent.
    _record_bench_samples("baseline", 100.0, 5, "half", tmp_path)

    r = _run("bench_compare.py", ["compare", "half"], tmp_path)
    assert r.returncode == 3, r.stderr


def test_bench_run_no_command_after_dashdash_exit_3(tmp_path: Path) -> None:
    # Provide `--` but nothing after it; bench_compare splits on `--` so args.cmd is empty.
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "bench_compare.py"),
            "run",
            "mybench",
            "--label",
            "x",
            "--",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=_env(tmp_path),
    )
    assert r.returncode == 3, r.stderr


def test_bench_bogus_flag_exit_3(tmp_path: Path) -> None:
    r = _run("bench_compare.py", ["--nonexistent-flag"], tmp_path)
    assert r.returncode == 3, r.stderr
