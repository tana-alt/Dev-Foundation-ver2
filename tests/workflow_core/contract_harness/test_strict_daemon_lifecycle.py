from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .conftest import FOUNDATIOND, HARNESS, git, start_daemon, strict_env


def test_strict_daemon_ping_and_stop(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        ping = subprocess.run(
            [str(HARNESS), "daemon", "ping"],
            cwd=harness_repo,
            capture_output=True,
            text=True,
            timeout=20,
            env=daemon.env,
        )
        assert ping.returncode == 0, ping.stdout + ping.stderr
        response = json.loads(ping.stdout)
        assert response["ok"] is True
        assert response["result"]["status"] == "running"
    finally:
        daemon.stop()
    assert daemon.process.poll() == 0


def test_strict_foundationd_status_and_stop(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    status = subprocess.run(
        [str(FOUNDATIOND), "status", "--repo", str(harness_repo)],
        cwd=harness_repo,
        capture_output=True,
        text=True,
        timeout=20,
        env=daemon.env,
    )
    assert status.returncode == 0, status.stdout + status.stderr
    response = json.loads(status.stdout)
    assert response["ok"] is True
    assert response["result"]["daemon"]["running"] is True

    stopped = subprocess.run(
        [str(FOUNDATIOND), "stop", "--repo", str(harness_repo)],
        cwd=harness_repo,
        capture_output=True,
        text=True,
        timeout=20,
        env=daemon.env,
    )
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr
    daemon.process.wait(timeout=20)


def test_strict_second_daemon_is_rejected(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        second = subprocess.run(
            [str(FOUNDATIOND), "run", "--foreground", "--repo", str(harness_repo)],
            cwd=harness_repo,
            capture_output=True,
            text=True,
            timeout=20,
            env=daemon.env,
        )
        assert second.returncode != 0
        response = json.loads(second.stderr)
        assert response["error"]["code"] == "conflict"
    finally:
        daemon.stop()


def test_strict_state_db_permissions_are_restrictive(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        env = strict_env(harness_repo)
        common = Path(git(harness_repo, "rev-parse", "--git-common-dir").stdout.strip())
        if not common.is_absolute():
            common = harness_repo / common
        runtime = Path(env.get("HARNESS_RUNTIME_ROOT", str(common / "harness-runtime")))
        mode = (runtime / "state" / "workflow-state.db").stat().st_mode & 0o777
        assert mode == 0o600
    finally:
        daemon.stop()
