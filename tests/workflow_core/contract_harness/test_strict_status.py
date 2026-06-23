from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .conftest import (
    TASK_ID,
    create_session,
    git,
    start_daemon,
    strict_cli,
    strict_env,
    strict_json,
)


def test_strict_status_includes_daemon_mode(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        status = strict_json(harness_repo, "status", TASK_ID, session=writer)

        assert status["ok"] is True
        assert status["result"]["mode"] == "local-strict"
        assert status["result"]["daemon"]["running"] is True
    finally:
        daemon.stop()


def test_strict_degraded_mode_blocks_writes(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        assert strict_cli(harness_repo, "prepare", TASK_ID, session=writer).returncode == 0
    finally:
        daemon.stop()

    db_path = _state_db_path(harness_repo)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE events SET payload_sha256 = 'sha256:tampered' WHERE id = 1")

    daemon = start_daemon(harness_repo)
    try:
        status = strict_json(harness_repo, "status", TASK_ID, session=writer)
        assert status["result"]["mode"] == "degraded"

        blocked = strict_cli(harness_repo, "submit", TASK_ID, session=writer)
        assert blocked.returncode == 1
        response = json.loads(blocked.stdout)
        assert response["error"]["code"] == "integrity_error"
    finally:
        daemon.stop()


def _state_db_path(repo: Path) -> Path:
    env = strict_env(repo)
    if "HARNESS_RUNTIME_ROOT" in env:
        return Path(env["HARNESS_RUNTIME_ROOT"]) / "state" / "workflow-state.db"
    common = Path(git(repo, "rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = repo / common
    return common / "harness-runtime" / "state" / "workflow-state.db"
