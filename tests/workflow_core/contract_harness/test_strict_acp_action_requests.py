from __future__ import annotations

from pathlib import Path

import pytest

from workflow_core.contract_harness.daemon.client import DaemonClient

from .conftest import TASK_ID, create_session, start_daemon, strict_cli, strict_json


def test_strict_acp_request_action_outputs_proposal_only(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")
        assert strict_cli(harness_repo, "prepare", TASK_ID, session=writer).returncode == 0
        before = strict_json(harness_repo, "status", TASK_ID, session=writer)

        proposal = strict_json(
            harness_repo,
            "acp",
            "request-action",
            "msg_1",
            "--body",
            "please verify this candidate",
            session=writer,
        )
        after = strict_json(harness_repo, "status", TASK_ID, session=writer)

        assert proposal["result"]["proposed_action"] == "candidate.verify"
        assert proposal["result"]["executed"] is False
        assert (
            after["result"]["state_store"]["current_phase"]
            == before["result"]["state_store"]["current_phase"]
        )
    finally:
        daemon.stop()


def test_strict_acp_send_uses_authenticated_session_agent_id(harness_repo: Path) -> None:
    daemon = start_daemon(harness_repo)
    try:
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")

        sent = strict_json(
            harness_repo,
            "acp",
            "send",
            TASK_ID,
            "--to-agent",
            "reviewer.scope.T-0001",
            "--to-role",
            "reviewer",
            "--kind",
            "clarification",
            "--subject",
            "review handoff",
            "--body",
            "please review the current candidate",
            session=writer,
        )
        inbox = strict_json(
            harness_repo,
            "acp",
            "list",
            TASK_ID,
            "--agent-id",
            "reviewer.scope.T-0001",
            session=writer,
        )

        assert sent["result"]["from"]["agent_id"] == writer.agent_id
        message = inbox["result"]["messages"][0]
        assert message["from"]["agent_id"] == writer.agent_id
    finally:
        daemon.stop()


def test_strict_acp_send_ignores_spoofed_from_fields(
    harness_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    daemon = start_daemon(harness_repo)
    try:
        if "HARNESS_RUNTIME_ROOT" in daemon.env:
            monkeypatch.setenv("HARNESS_RUNTIME_ROOT", daemon.env["HARNESS_RUNTIME_ROOT"])
        writer = create_session(harness_repo, "writer", agent_id="writer.codex.T-0001")

        response = DaemonClient.for_repo(harness_repo).request(
            "acp.send",
            {
                "task_id": TASK_ID,
                "to_agent_id": "reviewer.scope.T-0001",
                "to_role": "reviewer",
                "kind": "clarification",
                "subject": "spoof check",
                "body": "please review",
                "from_agent_id": "integrator.spoof.T-0001",
                "from_role": "integrator",
            },
            session_id=writer.session_id,
            capability_token=writer.capability_token,
        )

        assert response.ok is True
        assert response.result is not None
        assert response.result["from"]["agent_id"] == writer.agent_id
        assert response.result["from"]["role"] == writer.role
    finally:
        daemon.stop()
