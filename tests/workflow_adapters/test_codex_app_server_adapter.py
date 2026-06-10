from pathlib import Path

import pytest
import yaml

from src.workflow_adapters.codex_app_server_adapter import (
    AppServerRunEvent,
    AppServerThreadLink,
    HumanGateRequired,
    connect_real_app_server,
    map_run_event,
    map_thread_link,
)

ROOT = Path(__file__).resolve().parents[2]


def test_thread_link_maps_external_ref_without_state_authority_shift() -> None:
    record = map_thread_link(
        AppServerThreadLink(
            project_id="workflow-ui-commondb-20260608",
            execution_run_id="RUN-demo-001",
            app_server_thread_ref="app-server-thread:demo-thread",
        )
    )

    assert record["state_authority"] == "workflow_core"
    assert record["transport"] == "stdio"
    assert record["stores_raw_thread_body"] is False
    assert record["stores_credentials"] is False


def test_run_event_rejects_unbounded_summary() -> None:
    with pytest.raises(ValueError, match="bounded"):
        map_run_event(
            AppServerRunEvent(
                project_id="workflow-ui-commondb-20260608",
                execution_run_id="RUN-demo-001",
                event_id="EVT-demo-001",
                kind="event_received",
                status="observed",
                summary="x" * 161,
                external_event_ref="app-server-event:demo-event",
            )
        )


def test_real_bridge_is_human_gated() -> None:
    with pytest.raises(HumanGateRequired, match="human approval"):
        connect_real_app_server()


def test_app_server_templates_keep_denied_evidence_out() -> None:
    template_paths = [
        ROOT / "templates/app-server-thread-link.yaml",
        ROOT / "templates/app-server-run-event.yaml",
    ]

    for template_path in template_paths:
        data = yaml.safe_load(template_path.read_text())
        assert data["workflow_core"]["state_authority"] == "workflow_core"
        assert data["evidence_limits"]["stores_raw_thread_body"] is False
        assert data["evidence_limits"]["stores_credentials"] is False
