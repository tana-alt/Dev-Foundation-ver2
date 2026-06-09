"""Mock-safe Codex App Server adapter boundary.

The real bridge is intentionally human-gated. This module only maps sanitized
external refs into workflow UI records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast


class HumanGateRequired(RuntimeError):
    """Raised when code attempts to use the real App Server bridge locally."""


Transport = Literal["stdio", "http"]
EventKind = Literal[
    "thread_linked",
    "turn_started",
    "event_received",
    "approval_requested",
    "user_input_requested",
    "blocked",
    "error",
    "verification_recorded",
    "handoff_recorded",
    "spec_amendment_requested",
    "spec_amendment_approved",
]
EVENT_KINDS: set[str] = {
    "thread_linked",
    "turn_started",
    "event_received",
    "approval_requested",
    "user_input_requested",
    "blocked",
    "error",
    "verification_recorded",
    "handoff_recorded",
    "spec_amendment_requested",
    "spec_amendment_approved",
}
EVENT_STATUSES = {"observed", "blocked", "skipped"}


@dataclass(frozen=True)
class AppServerThreadLink:
    project_id: str
    execution_run_id: str
    app_server_thread_ref: str
    transport: Transport = "stdio"


@dataclass(frozen=True)
class AppServerRunEvent:
    project_id: str
    execution_run_id: str
    event_id: str
    kind: EventKind
    status: Literal["observed", "blocked", "skipped"]
    summary: str
    external_event_ref: str


@dataclass(frozen=True)
class AppServerProjectLink:
    project_id: str
    workflow_id: str
    app_server_thread_ref: str
    codex_app_link_ref: str
    artifact_refs: tuple[str, ...]
    link_status: Literal["linked", "missing", "gated"]
    latest_event_summary: str
    transport: Transport = "stdio"


def _require_opaque_ref(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise ValueError(f"external ref must start with {prefix}")
    if "\n" in value or "\r" in value:
        raise ValueError("external ref must be a single line")
    return value


def _require_allowed_artifact_ref(value: str) -> str:
    allowed_prefixes = ("codex-app-artifact:", "github-pr:")
    if not value.startswith(allowed_prefixes):
        raise ValueError("artifact ref must be a supported opaque ref")
    if "\n" in value or "\r" in value:
        raise ValueError("artifact ref must be a single line")
    return value


def map_project_link(link: AppServerProjectLink) -> dict[str, object]:
    if len(link.latest_event_summary) > 160:
        raise ValueError("latest event summary must stay bounded")
    return {
        "record_type": "app_server_project_link",
        "project_id": link.project_id,
        "workflow_id": link.workflow_id,
        "app_server_thread_ref": _require_opaque_ref(
            link.app_server_thread_ref,
            "app-server-thread:",
        ),
        "codex_app_link_ref": _require_opaque_ref(
            link.codex_app_link_ref,
            "codex-app-link:",
        ),
        "artifact_refs": [_require_allowed_artifact_ref(ref) for ref in link.artifact_refs],
        "link_status": link.link_status,
        "latest_event_summary": link.latest_event_summary,
        "transport": link.transport,
        "state_authority": "workflow_core",
        "stores_raw_thread_body": False,
        "stores_artifact_contents": False,
        "stores_credentials": False,
    }


def map_thread_link(link: AppServerThreadLink) -> dict[str, object]:
    return {
        "record_type": "app_server_thread_link",
        "project_id": link.project_id,
        "execution_run_id": link.execution_run_id,
        "app_server_thread_ref": _require_opaque_ref(
            link.app_server_thread_ref,
            "app-server-thread:",
        ),
        "transport": link.transport,
        "state_authority": "workflow_core",
        "stores_raw_thread_body": False,
        "stores_credentials": False,
    }


def map_run_event(event: AppServerRunEvent) -> dict[str, object]:
    if event.kind not in EVENT_KINDS:
        raise ValueError("unsupported app server event kind")
    if event.status not in EVENT_STATUSES:
        raise ValueError("unsupported app server event status")
    if len(event.summary) > 160:
        raise ValueError("event summary must stay bounded")
    return {
        "record_type": "app_server_run_event",
        "project_id": event.project_id,
        "execution_run_id": event.execution_run_id,
        "event_id": event.event_id,
        "kind": event.kind,
        "status": event.status,
        "summary": event.summary,
        "external_event_ref": _require_opaque_ref(
            event.external_event_ref,
            "app-server-event:",
        ),
        "state_authority": "workflow_core",
        "stores_raw_thread_body": False,
        "stores_raw_terminal_log": False,
    }


def map_jsonrpc_notification(
    payload: dict[str, Any],
    *,
    project_id: str,
    execution_run_id: str,
) -> AppServerRunEvent:
    if payload.get("jsonrpc") != "2.0":
        raise ValueError("jsonrpc notification must declare version 2.0")
    if payload.get("method") != "app_server.event":
        raise ValueError("unsupported app server notification method")
    params = payload.get("params")
    if not isinstance(params, dict):
        raise ValueError("jsonrpc notification params must be a mapping")
    params_data = cast(dict[str, Any], params)

    kind = _required_param(params_data, "kind")
    status = _required_param(params_data, "status")
    if kind not in EVENT_KINDS:
        raise ValueError("unsupported app server event kind")
    if status not in EVENT_STATUSES:
        raise ValueError("unsupported app server event status")

    return AppServerRunEvent(
        project_id=project_id,
        execution_run_id=execution_run_id,
        event_id=_required_param(params_data, "event_id"),
        kind=cast(EventKind, kind),
        status=cast(
            Literal["observed", "blocked", "skipped"],
            status,
        ),
        summary=_required_param(params_data, "summary"),
        external_event_ref=_required_param(params_data, "external_event_ref"),
    )


def build_app_server_ui_panel(
    link: AppServerThreadLink,
    events: tuple[AppServerRunEvent, ...],
) -> dict[str, object]:
    mapped_link = map_thread_link(link)
    mapped_events = [map_run_event(event) for event in events]
    return {
        "thread_ref": mapped_link["app_server_thread_ref"],
        "transport": mapped_link["transport"],
        "gate_status": "required",
        "real_smoke_status": "skipped_human_gate_required",
        "events": [
            {
                "event_id": event["event_id"],
                "kind": event["kind"],
                "status": event["status"],
                "summary": event["summary"],
                "external_event_ref": event["external_event_ref"],
            }
            for event in mapped_events
        ],
    }


def connect_real_app_server() -> None:
    raise HumanGateRequired("Real App Server bridge requires explicit human approval.")


def _required_param(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single line")
    return value
