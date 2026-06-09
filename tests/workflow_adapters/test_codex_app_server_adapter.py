from pathlib import Path

import pytest
import yaml

from src.workflow_adapters.codex_app_server_adapter import (
    AppServerProjectLink,
    AppServerRunEvent,
    AppServerThreadLink,
    HumanGateRequired,
    build_app_server_ui_panel,
    connect_real_app_server,
    map_jsonrpc_notification,
    map_project_link,
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


def test_project_link_maps_codex_app_navigation_without_raw_contents() -> None:
    record = map_project_link(
        AppServerProjectLink(
            project_id="workflow-ui-commondb-20260608",
            workflow_id="codex-app-vertical-integration-20260609",
            app_server_thread_ref="app-server-thread:demo-thread",
            codex_app_link_ref="codex-app-link:workflow-ui-commondb-demo",
            artifact_refs=("codex-app-artifact:workflow-console-html", "github-pr:19"),
            link_status="linked",
            latest_event_summary="Project link is available.",
        )
    )

    assert record["record_type"] == "app_server_project_link"
    assert record["state_authority"] == "workflow_core"
    assert record["codex_app_link_ref"] == "codex-app-link:workflow-ui-commondb-demo"
    assert record["artifact_refs"] == ["codex-app-artifact:workflow-console-html", "github-pr:19"]
    assert record["stores_raw_thread_body"] is False
    assert record["stores_artifact_contents"] is False
    assert record["stores_credentials"] is False


def test_project_link_rejects_unapproved_artifact_ref() -> None:
    with pytest.raises(ValueError, match="artifact ref"):
        map_project_link(
            AppServerProjectLink(
                project_id="workflow-ui-commondb-20260608",
                workflow_id="codex-app-vertical-integration-20260609",
                app_server_thread_ref="app-server-thread:demo-thread",
                codex_app_link_ref="codex-app-link:workflow-ui-commondb-demo",
                artifact_refs=("file:///tmp/raw.html",),
                link_status="linked",
                latest_event_summary="Unsafe artifact ref.",
            )
        )


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


def test_jsonrpc_notification_maps_to_sanitized_run_event() -> None:
    event = map_jsonrpc_notification(
        {
            "jsonrpc": "2.0",
            "method": "app_server.event",
            "params": {
                "event_id": "EVT-demo-001",
                "kind": "approval_requested",
                "status": "blocked",
                "summary": "Approval is required before the bridge can run.",
                "external_event_ref": "app-server-event:approval-requested",
            },
        },
        project_id="workflow-ui-commondb-20260608",
        execution_run_id="RUN-demo-001",
    )

    record = map_run_event(event)

    assert record["kind"] == "approval_requested"
    assert record["status"] == "blocked"
    assert record["external_event_ref"] == "app-server-event:approval-requested"
    assert record["stores_raw_terminal_log"] is False


def test_jsonrpc_notification_rejects_unknown_event_kind() -> None:
    with pytest.raises(ValueError, match="event kind"):
        map_jsonrpc_notification(
            {
                "jsonrpc": "2.0",
                "method": "app_server.event",
                "params": {
                    "event_id": "EVT-demo-001",
                    "kind": "raw_dump",
                    "status": "observed",
                    "summary": "Unsafe event kind.",
                    "external_event_ref": "app-server-event:unsafe",
                },
            },
            project_id="workflow-ui-commondb-20260608",
            execution_run_id="RUN-demo-001",
        )


def test_app_server_ui_panel_projects_events_without_state_authority_shift() -> None:
    panel = build_app_server_ui_panel(
        AppServerThreadLink(
            project_id="workflow-ui-commondb-20260608",
            execution_run_id="RUN-demo-001",
            app_server_thread_ref="app-server-thread:demo-thread",
        ),
        (
            AppServerRunEvent(
                project_id="workflow-ui-commondb-20260608",
                execution_run_id="RUN-demo-001",
                event_id="EVT-demo-001",
                kind="thread_linked",
                status="observed",
                summary="Thread link observed.",
                external_event_ref="app-server-event:thread-linked",
            ),
        ),
    )

    assert panel["thread_ref"] == "app-server-thread:demo-thread"
    assert panel["transport"] == "stdio"
    assert panel["gate_status"] == "required"
    assert panel["real_smoke_status"] == "skipped_human_gate_required"
    assert panel["events"] == [
        {
            "event_id": "EVT-demo-001",
            "kind": "thread_linked",
            "status": "observed",
            "summary": "Thread link observed.",
            "external_event_ref": "app-server-event:thread-linked",
        }
    ]


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
