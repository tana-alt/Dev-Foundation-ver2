"""Plan-N0002 R15 Phase 1 acceptance: abrun -> verdict -> gate end to end.

Mini suite over a scratch git repo with deterministic stdout-metric values:
- seeded regression  -> gate exit 1
- neutral refactor   -> gate exit 0
- noisy straddle     -> gate exit 2 (retry budget left) and verdict exit 2
  with suggested_additional_iterations in the JSON output.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Pinned datasets shared with tests/workflow_core/test_verdict.py.
BASE = [100.0, 101.0, 99.0, 100.5, 100.2, 99.8, 100.1, 100.3, 99.9, 100.0]
REGRESS = [112.0, 113.0, 111.0, 112.5, 112.2, 111.8, 112.1, 112.3, 111.9, 112.0]
STRADDLE = [104.0, 106.0, 103.0, 108.0, 102.0, 107.0, 105.0, 104.5, 105.5, 106.5]

MEASURE_TEMPLATE = """{comment}import os
VALUES = {values}
print(VALUES[int(os.environ["ABRUN_ITERATION"]) % len(VALUES)])
"""

POLICY = {
    "policy_version": 1,
    "conditions": [
        {"tool": "check", "metric": "overall", "require": "pass"},
        {
            "tool": "verdict",
            "metric": "demo.value",
            "mode": "non_regression",
            "threshold_pct": 5.0,
        },
    ],
    "on_inconclusive": "retry_then_fail",
    "max_retries": 2,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "FOUNDATION_REPO_ROOT": str(tmp_path / "harness"),
        "FOUNDATION_PROJECT_ID": "t",
        "FOUNDATION_POLICY_DIR": str(tmp_path / "policies"),
    }


def run_cli(script: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def commit_measure(repo: Path, values: list[float], comment: str = "") -> None:
    script = MEASURE_TEMPLATE.format(values=values, comment=comment)
    (repo / "measure.py").write_text(script, encoding="utf-8")
    git(repo, "commit", "-am", "update measure")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """main prints BASE; branches regress/neutral/straddle vary the values."""
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True, text=True
    )
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    (path / "measure.py").write_text(
        MEASURE_TEMPLATE.format(values=BASE, comment=""), encoding="utf-8"
    )
    git(path, "add", "measure.py")
    git(path, "commit", "-m", "baseline")
    for branch, values, comment in (
        ("regress", REGRESS, ""),
        ("neutral", BASE, "# perf-neutral refactor\n"),
        ("straddle", STRADDLE, ""),
    ):
        git(path, "checkout", "-b", branch, "main")
        commit_measure(path, values, comment)
    git(path, "checkout", "main")
    return path


def write_policy(tmp_path: Path) -> Path:
    directory = tmp_path / "policies"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "ab.json"
    path.write_text(json.dumps(POLICY), encoding="utf-8")
    return path


def run_pipeline(
    tmp_path: Path, repo: Path, env: dict[str, str], case: str, candidate_ref: str
) -> tuple[str, str]:
    """abrun + check_runner for one case; returns (baseline_run_id, candidate_run_id)."""
    config = {
        "baseline": {"ref": "main", "worktree": str(tmp_path / "wts" / f"{case}-base")},
        "candidate": {
            "ref": candidate_ref,
            "worktree": str(tmp_path / "wts" / f"{case}-cand"),
        },
        "measure": {
            "tool": "command",
            "command": [sys.executable, "measure.py"],
            "metric": "demo.value",
            "value_from": "stdout",
        },
        "iterations": 10,
        "warmup": 0,
    }
    config_path = tmp_path / f"ab-{case}.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    measured = run_cli("abrun.py", ["run", "--config", str(config_path), "--repo", str(repo)], env)
    assert measured.returncode == 0, measured.stderr
    result = json.loads(measured.stdout)
    smoke = f"smoke={shlex.quote(sys.executable)} -c pass"
    checked = run_cli(
        "check_runner.py",
        [
            "run",
            "--run-id",
            result["candidate_run_id"],
            "--worktree",
            config["candidate"]["worktree"],  # type: ignore[index]
            "--cmd",
            smoke,
        ],
        env,
    )
    assert checked.returncode == 0, checked.stderr
    return result["baseline_run_id"], result["candidate_run_id"]


def evaluate(
    policy: Path, base_run: str, cand_run: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return run_cli(
        "quality_gate.py",
        [
            "evaluate",
            "--policy",
            str(policy),
            "--baseline-run",
            base_run,
            "--candidate-run",
            cand_run,
            "--resamples",
            "1500",
        ],
        env,
    )


# ---------------------------------------------------------------------------
# R15 acceptance criteria
# ---------------------------------------------------------------------------


def test_seeded_regression_exits_1(tmp_path: Path, repo: Path) -> None:
    env = make_env(tmp_path)
    policy = write_policy(tmp_path)
    base_run, cand_run = run_pipeline(tmp_path, repo, env, "regress", "regress")
    gate = evaluate(policy, base_run, cand_run, env)
    assert gate.returncode == 1, gate.stdout + gate.stderr
    report = json.loads(gate.stdout)
    assert report["result"] == "fail"
    by_metric = {c["metric"]: c["result"] for c in report["conditions"]}
    assert by_metric == {"overall": "pass", "demo.value": "regression"}


def test_neutral_exits_0(tmp_path: Path, repo: Path) -> None:
    env = make_env(tmp_path)
    policy = write_policy(tmp_path)
    base_run, cand_run = run_pipeline(tmp_path, repo, env, "neutral", "neutral")
    gate = evaluate(policy, base_run, cand_run, env)
    assert gate.returncode == 0, gate.stdout + gate.stderr
    assert json.loads(gate.stdout)["result"] == "pass"


def test_inconclusive_exits_2_with_suggestion(tmp_path: Path, repo: Path) -> None:
    env = make_env(tmp_path)
    policy = write_policy(tmp_path)
    base_run, cand_run = run_pipeline(tmp_path, repo, env, "straddle", "straddle")
    gate = evaluate(policy, base_run, cand_run, env)
    assert gate.returncode == 2, gate.stdout + gate.stderr
    assert json.loads(gate.stdout)["result"] == "inconclusive"
    verdict = run_cli(
        "verdict.py",
        [
            "compare",
            "--baseline-run",
            base_run,
            "--candidate-run",
            cand_run,
            "--metric",
            "demo.value",
            "--policy",
            str(policy),
            "--resamples",
            "1500",
        ],
        env,
    )
    assert verdict.returncode == 2, verdict.stdout + verdict.stderr
    payload = json.loads(verdict.stdout)
    assert payload["result"] == "inconclusive"
    assert isinstance(payload["suggested_additional_iterations"], int)
    assert payload["repro"].startswith("verdict compare")


def test_policy_outside_allowed_dir_exits_3(tmp_path: Path, repo: Path) -> None:
    env = make_env(tmp_path)
    rogue = tmp_path / "rogue" / "p.json"
    rogue.parent.mkdir(parents=True)
    rogue.write_text(json.dumps(POLICY), encoding="utf-8")
    gate = run_cli(
        "quality_gate.py",
        ["evaluate", "--policy", str(rogue), "--baseline-run", "x", "--candidate-run", "y"],
        env,
    )
    assert gate.returncode == 3
    assert "outside the allowed policy dir" in gate.stderr
