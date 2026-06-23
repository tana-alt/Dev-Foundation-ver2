from __future__ import annotations

from pathlib import Path

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
