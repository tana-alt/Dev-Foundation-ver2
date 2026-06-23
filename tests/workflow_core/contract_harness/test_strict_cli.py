from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from .conftest import TASK_ID, create_session, start_daemon, strict_cli, strict_env


def test_strict_cli_fails_when_daemon_unavailable(harness_repo: Path) -> None:
    completed = strict_cli(harness_repo, "status", TASK_ID)

    assert completed.returncode == 1
    response = json.loads(completed.stdout)
    assert response["error"]["code"] == "daemon_unavailable"

    env = strict_env(harness_repo)
    runtime = Path(env.get("HARNESS_RUNTIME_ROOT", str(harness_repo / ".git" / "harness-runtime")))
    assert not (runtime / "state" / "workflow-state.db").exists()


def test_strict_cli_does_not_construct_state_or_evidence_store(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daemon = start_daemon(harness_repo)
    try:
        session = create_session(
            harness_repo,
            "writer",
            agent_id="writer.codex.T-0001",
        )
        from workflow_core.contract_harness.adapters.filesystem_evidence_store import (
            FilesystemEvidenceStore,
        )
        from workflow_core.contract_harness.adapters.sqlite_state_store import SQLiteStateStore
        from workflow_core.contract_harness.cli import main

        def fail_init(*_args: Any, **_kwargs: Any) -> None:
            raise AssertionError("strict CLI constructed local storage")

        monkeypatch.setattr(SQLiteStateStore, "__init__", fail_init)
        monkeypatch.setattr(FilesystemEvidenceStore, "__init__", fail_init)
        monkeypatch.chdir(harness_repo)
        monkeypatch.setenv("FOUNDATION_SESSION_ID", session.session_id)
        monkeypatch.setenv("FOUNDATION_CAPABILITY_TOKEN", session.capability_token)
        for key, value in daemon.env.items():
            if key == "HARNESS_RUNTIME_ROOT":
                monkeypatch.setenv(key, value)

        assert main(["--strict", "status", TASK_ID]) == 0
    finally:
        daemon.stop()
