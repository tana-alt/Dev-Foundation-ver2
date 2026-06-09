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
    "conversation_linked",
    "execution_started",
    "artifact_reviewed",
    "handoff_accepted",
    "verification_submitted",
    "approval_observed",
    "completion_requested",
    "completion_blocked",
    "scope_amendment_accepted",
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
EventStatus = Literal["observed", "blocked", "skipped", "rejected"]
ActorCategory = Literal["agent", "human", "system", "workflow_core", "unknown"]
SourceSurface = Literal[
    "codex_app_server",
    "codex_app",
    "workflow_ui",
    "workflow_core",
    "cli",
    "unknown",
]
HumanGateStatus = Literal[
    "not_applicable",
    "required",
    "approved",
    "blocked",
    "changes_requested",
]
EVENT_KINDS: set[str] = {
    "conversation_linked",
    "execution_started",
    "artifact_reviewed",
    "handoff_accepted",
    "verification_submitted",
    "approval_observed",
    "completion_requested",
    "completion_blocked",
    "scope_amendment_accepted",
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
EVENT_STATUSES = {"observed", "blocked", "skipped", "rejected"}
ACTOR_CATEGORIES = {"agent", "human", "system", "workflow_core", "unknown"}
SOURCE_SURFACES = {
    "codex_app_server",
    "codex_app",
    "workflow_ui",
    "workflow_core",
    "cli",
    "unknown",
}
HUMAN_GATE_STATUSES = {
    "not_applicable",
    "required",
    "approved",
    "blocked",
    "changes_requested",
}
COMPLETION_EVENT_KINDS = {"completion_requested", "completion_blocked"}
WORKFLOW_STATE_REFS = {
    "unknown",
    "linked",
    "ready",
    "running",
    "review",
    "handoff",
    "scope_amendment",
    "complete",
    "blocked",
}
EVIDENCE_REF_PREFIXES = (
    "artifact/",
    "Plan/",
    "docs/",
    "src/",
    "tests/",
    "user_request:",
    "command:",
    "test:",
    "workflow-core:",
)


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
    status: EventStatus
    summary: str
    external_event_ref: str
    previous_state: str = "unknown"
    requested_next_state: str = "unknown"
    actor_category: ActorCategory = "unknown"
    source_surface: SourceSurface = "codex_app_server"
    human_gate_status: HumanGateStatus = "not_applicable"
    evidence_refs: tuple[str, ...] = ()
    workflow_core_completion_prerequisites_met: bool = False


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


def _require_supported_state_ref(value: str, field_name: str) -> str:
    if value not in WORKFLOW_STATE_REFS:
        raise ValueError(f"{field_name} must be a supported workflow state ref")
    return value


def _require_supported_evidence_ref(value: str) -> str:
    if not value.startswith(EVIDENCE_REF_PREFIXES):
        raise ValueError("evidence ref must be a supported opaque or repo ref")
    if "\n" in value or "\r" in value:
        raise ValueError("evidence ref must be a single line")
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
        "stores_browser_sessions": False,
        "stores_local_runtime_state": False,
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
        "stores_browser_sessions": False,
        "stores_local_runtime_state": False,
    }


def map_run_event(event: AppServerRunEvent) -> dict[str, object]:
    if event.kind not in EVENT_KINDS:
        raise ValueError("unsupported app server event kind")
    if event.status not in EVENT_STATUSES:
        raise ValueError("unsupported app server event status")
    if event.actor_category not in ACTOR_CATEGORIES:
        raise ValueError("unsupported app server actor category")
    if event.source_surface not in SOURCE_SURFACES:
        raise ValueError("unsupported app server source surface")
    if event.human_gate_status not in HUMAN_GATE_STATUSES:
        raise ValueError("unsupported app server human gate status")
    if len(event.summary) > 160:
        raise ValueError("event summary must stay bounded")
    previous_state = _require_supported_state_ref(
        event.previous_state,
        "previous_state",
    )
    requested_next_state = _require_supported_state_ref(
        event.requested_next_state,
        "requested_next_state",
    )
    evidence_refs = [_require_supported_evidence_ref(ref) for ref in event.evidence_refs]
    status: EventStatus = event.status
    completion_claim_guard = "not_applicable"
    completion_prerequisites_met = False
    if requested_next_state == "complete" or event.kind in COMPLETION_EVENT_KINDS:
        status = "blocked"
        completion_claim_guard = "blocked_authority_preserved"
    return {
        "record_type": "app_server_run_event",
        "project_id": event.project_id,
        "execution_run_id": event.execution_run_id,
        "event_id": _required_param({"event_id": event.event_id}, "event_id"),
        "kind": event.kind,
        "status": status,
        "summary": event.summary,
        "external_event_ref": _require_opaque_ref(
            event.external_event_ref,
            "app-server-event:",
        ),
        "previous_state": previous_state,
        "requested_next_state": requested_next_state,
        "actor_category": event.actor_category,
        "source_surface": event.source_surface,
        "human_gate_status": event.human_gate_status,
        "evidence_refs": evidence_refs,
        "state_authority": "workflow_core",
        "authority_boundary": "observation_only",
        "approval_authority": "workflow_core",
        "verification_authority": "workflow_core",
        "handoff_authority": "workflow_core",
        "scope_amendment_authority": "workflow_core",
        "completion_authority": "workflow_core",
        "establishes_approval": False,
        "establishes_verification": False,
        "establishes_handoff": False,
        "establishes_scope_amendment": False,
        "establishes_completion": False,
        "completion_claim_guard": completion_claim_guard,
        "workflow_core_completion_prerequisites_met": completion_prerequisites_met,
        "stores_raw_thread_body": False,
        "stores_raw_terminal_log": False,
        "stores_credentials": False,
        "stores_browser_sessions": False,
        "stores_local_runtime_state": False,
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
    evidence_refs = _optional_evidence_refs(params_data)

    return AppServerRunEvent(
        project_id=project_id,
        execution_run_id=execution_run_id,
        event_id=_required_param(params_data, "event_id"),
        kind=cast(EventKind, kind),
        status=cast(EventStatus, status),
        summary=_required_param(params_data, "summary"),
        external_event_ref=_required_param(params_data, "external_event_ref"),
        previous_state=_optional_param(params_data, "previous_state", "unknown"),
        requested_next_state=_optional_param(
            params_data,
            "requested_next_state",
            "unknown",
        ),
        actor_category=cast(
            ActorCategory,
            _optional_param(params_data, "actor_category", "unknown"),
        ),
        source_surface=cast(
            SourceSurface,
            _optional_param(params_data, "source_surface", "codex_app_server"),
        ),
        human_gate_status=cast(
            HumanGateStatus,
            _optional_param(params_data, "human_gate_status", "not_applicable"),
        ),
        evidence_refs=evidence_refs,
        workflow_core_completion_prerequisites_met=False,
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
                "previous_state": event["previous_state"],
                "requested_next_state": event["requested_next_state"],
                "actor_category": event["actor_category"],
                "source_surface": event["source_surface"],
                "human_gate_status": event["human_gate_status"],
                "evidence_refs": event["evidence_refs"],
                "completion_claim_guard": event["completion_claim_guard"],
                "authority_boundary": event["authority_boundary"],
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


def _optional_param(params: dict[str, Any], key: str, default: str) -> str:
    value = params.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single line")
    return value


def _optional_evidence_refs(params: dict[str, Any]) -> tuple[str, ...]:
    value = params.get("evidence_refs", ())
    if not isinstance(value, (list, tuple)):
        raise ValueError("evidence_refs must be a list")
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("evidence_refs must contain non-empty strings")
        refs.append(item)
    return tuple(refs)
