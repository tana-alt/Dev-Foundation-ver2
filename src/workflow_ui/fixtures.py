"""Sanitized fixture records for the local workflow console."""

from __future__ import annotations

from typing import Literal, TypedDict


class WorkflowRunEvent(TypedDict):
    event_id: str
    kind: str
    status: Literal["observed", "blocked", "skipped"]
    summary: str
    external_event_ref: str


class AppServerUiPanel(TypedDict):
    thread_ref: str
    transport: Literal["stdio", "http"]
    gate_status: Literal["required", "approved", "blocked", "not_applicable"]
    real_smoke_status: str
    events: list[WorkflowRunEvent]


class WorkflowRun(TypedDict):
    issue_id: str
    title: str
    proposal_summary: str
    approved_contract_ref: str
    execution_run_ref: str
    execution_status: Literal["planned", "running", "blocked", "complete"]
    runner: Literal["mock", "sdk", "app_server"]
    verification_result: Literal["passed", "failed", "blocked", "skipped"]
    handoff_status: Literal["draft", "ready_for_review", "blocked"]
    external_refs: list[str]
    app_server: AppServerUiPanel


def load_sanitized_runs() -> list[WorkflowRun]:
    execution_run_ref = (
        "artifact/workflow-ui-commondb-20260608/output/demos/demo-workflow-001/run.yaml"
    )
    return [
        {
            "issue_id": "ISSUE-demo-001",
            "title": "Render workflow run from sanitized records",
            "proposal_summary": "Use the mock console to inspect a bounded execution run.",
            "approved_contract_ref": "templates/approved-work-contract.yaml",
            "execution_run_ref": execution_run_ref,
            "execution_status": "blocked",
            "runner": "app_server",
            "verification_result": "skipped",
            "handoff_status": "draft",
            "external_refs": ["app-server-thread:demo-thread"],
            "app_server": {
                "thread_ref": "app-server-thread:demo-thread",
                "transport": "stdio",
                "gate_status": "required",
                "real_smoke_status": "skipped_human_gate_required",
                "events": [
                    {
                        "event_id": "EVT-demo-001",
                        "kind": "thread_linked",
                        "status": "observed",
                        "summary": "Demo thread reference attached to the execution run.",
                        "external_event_ref": "app-server-event:demo-thread-linked",
                    },
                    {
                        "event_id": "EVT-demo-002",
                        "kind": "approval_requested",
                        "status": "blocked",
                        "summary": "Real bridge remains paused until explicit approval.",
                        "external_event_ref": "app-server-event:demo-approval-requested",
                    },
                ],
            },
        }
    ]
