"""Mock-safe Codex App Server adapter boundary.

The real bridge is intentionally human-gated. This module only maps sanitized
external refs into workflow UI records.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


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
]


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


def _require_opaque_ref(value: str, prefix: str) -> str:
    if not value.startswith(prefix):
        raise ValueError(f"external ref must start with {prefix}")
    if "\n" in value or "\r" in value:
        raise ValueError("external ref must be a single line")
    return value


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


def connect_real_app_server() -> None:
    raise HumanGateRequired("Real App Server bridge requires explicit human approval.")
