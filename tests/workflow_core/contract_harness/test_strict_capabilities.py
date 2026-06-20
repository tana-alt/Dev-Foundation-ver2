from __future__ import annotations

import json
from pathlib import Path

from .conftest import TASK_ID, create_session, root_token_for, start_daemon, strict_cli


def test_strict_session_create_requires_explicit_admin_authority(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        completed = strict_cli(
            harness_repo,
            "session",
            "create",
            "--role",
            "admin",
            "--task",
            TASK_ID,
            "--agent",
            "admin.local.T-0001",
            env={"FOUNDATION_ROOT_TOKEN": ""},
        )

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["error"]["code"] == "unauthorized"
    finally:
        daemon.stop()


def test_strict_writer_cannot_gate(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")

        completed = strict_cli(harness_repo, "gate", TASK_ID, session=writer)

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["error"]["code"] == "forbidden"
    finally:
        daemon.stop()


def test_strict_writer_cannot_pr_merge_or_complete(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")

        for args in [
            ("pr", "create", TASK_ID),
            ("merge", "local", TASK_ID),
            ("complete", TASK_ID),
        ]:
            completed = strict_cli(harness_repo, *args, session=writer)
            response = json.loads(completed.stdout)
            assert completed.returncode == 1
            assert response["error"]["code"] == "forbidden"
    finally:
        daemon.stop()


def test_strict_reviewer_cannot_submit_gate_or_complete(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        reviewer = create_session(harness_repo, "reviewer", agent_id="reviewer.scope.T-0001")

        for args in [
            ("submit", TASK_ID),
            ("gate", TASK_ID),
            ("complete", TASK_ID),
        ]:
            completed = strict_cli(harness_repo, *args, session=reviewer)
            response = json.loads(completed.stdout)
            assert completed.returncode == 1
            assert response["error"]["code"] == "forbidden"
    finally:
        daemon.stop()


def test_strict_integrator_push_routes_through_daemon_precondition(
    harness_repo: Path,
) -> None:
    daemon = start_daemon(harness_repo)
    try:
        integrator = create_session(
            harness_repo,
            "integrator",
            agent_id="integrator.codex.T-0001",
        )

        completed = strict_cli(harness_repo, "push", TASK_ID, session=integrator)

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["ok"] is True
        assert response["result"]["status"] == "failed"
        assert response["result"]["result"]["reason"] == "land_result_missing"
    finally:
        daemon.stop()


def test_strict_invalid_token_rejected(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        bad = writer.__class__(
            session_id=writer.session_id,
            capability_token="ftok_bad",
            role=writer.role,
            agent_id=writer.agent_id,
        )

        completed = strict_cli(harness_repo, "status", TASK_ID, session=bad)

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["error"]["code"] == "unauthorized"
    finally:
        daemon.stop()


def test_strict_revoked_session_rejected(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        revoked = strict_cli(
            harness_repo,
            "session",
            "revoke",
            writer.session_id,
            "--root-token",
            root_token_for(harness_repo),
        )
        assert revoked.returncode == 0, revoked.stdout + revoked.stderr

        completed = strict_cli(harness_repo, "status", TASK_ID, session=writer)

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["error"]["code"] == "unauthorized"
    finally:
        daemon.stop()


def test_strict_task_scoped_session_cannot_act_on_other_task(harness_repo: Path) -> None:
    task_dir = harness_repo / ".harness" / "tasks" / "T-0002"
    task_dir.mkdir(parents=True)
    (task_dir / "task.yaml").write_text(
        "id: T-0002\n"
        "scope: demo\n"
        "base: main\n"
        "intent:\n"
        "  kind: implementation\n"
        "  summary: second task\n"
        "acceptance:\n"
        "  mode: generated\n"
        "allowed_outputs:\n"
        "  - source_diff\n",
        encoding="utf-8",
    )
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")

        completed = strict_cli(harness_repo, "prepare", "T-0002", session=writer)

        assert completed.returncode == 1
        response = json.loads(completed.stdout)
        assert response["error"]["code"] == "forbidden"
    finally:
        daemon.stop()
