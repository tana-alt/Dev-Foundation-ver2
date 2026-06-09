"""Sanitized fixture records for the local workflow console."""

from __future__ import annotations

from typing import Literal, TypedDict


class WorkflowRunEvent(TypedDict):
    event_id: str
    kind: str
    status: Literal["observed", "blocked", "skipped"]
    summary: str
    external_event_ref: str


class GoalSetup(TypedDict):
    goal_id: str
    statement: str
    desired_outcome: str
    success_criteria: list[str]
    constraints: list[str]
    non_goals: list[str]
    denied_context: list[str]
    commondb_preference: Literal["disabled", "search_requested", "search_approved"]


class ProposalCandidate(TypedDict):
    candidate_id: str
    title: str
    status: Literal["available", "selected", "changes_requested", "approved", "rejected"]
    source_refs: list[str]
    risk_flags: list[str]
    verification: list[str]
    codex_app_ref: str


class CommonDBControls(TypedDict):
    search_permission: Literal["pending", "approved", "blocked"]
    searchable_destinations: list[Literal["useful_source", "approved_memo"]]
    source_refs: list[str]
    approved_memo_refs: list[str]
    excluded_refs: list[str]
    migration_approval: Literal["pending", "approved", "blocked"]
    stores_raw_body: bool


class ScopeGuard(TypedDict):
    status: Literal["within_spec", "spec_amendment_required", "blocked"]
    approved_spec_ref: str
    expansion_policy: str
    completion_policy: str


class AppServerUiPanel(TypedDict):
    project_id: str
    workflow_id: str
    thread_ref: str
    codex_app_link_ref: str
    artifact_refs: list[str]
    link_status: Literal["linked", "missing", "gated"]
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
    goal: GoalSetup
    candidates: list[ProposalCandidate]
    commondb: CommonDBControls
    scope_guard: ScopeGuard
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
            "goal": {
                "goal_id": "GOAL-codexapp-vertical-001",
                "statement": (
                    "Manage workflow state in custom UI while Codex App owns "
                    "conversation and artifact review."
                ),
                "desired_outcome": (
                    "A bounded state-management UI links directly to Codex App "
                    "and CommonDB approval controls."
                ),
                "success_criteria": [
                    "Goal setup state is visible.",
                    "Codex App project link state is visible.",
                    "CommonDB useful-source and approved-memo controls are visible.",
                    "Scope expansion is guarded by spec amendment state.",
                ],
                "constraints": [
                    "Do not store raw Codex thread bodies.",
                    "Do not make App Server the state authority.",
                ],
                "non_goals": [
                    "Do not recreate the Codex App chat interface.",
                    "Do not run the real App Server bridge without approval.",
                ],
                "denied_context": [
                    "conversation bodies",
                    "terminal transcripts",
                    "browser data",
                    "runtime machine state",
                ],
                "commondb_preference": "search_approved",
            },
            "candidates": [
                {
                    "candidate_id": "CAND-001",
                    "title": "State manager UI with Codex App project links",
                    "status": "selected",
                    "source_refs": [
                        "artifact/workflow-ui-commondb-20260608/output/specs/codex-app-vertical-integration-spec.md",
                    ],
                    "risk_flags": ["real_app_server_bridge_human_gate"],
                    "verification": [
                        "workflow UI tests",
                        "adapter boundary tests",
                        "check-fast",
                    ],
                    "codex_app_ref": "codex-app-link:workflow-ui-commondb-demo",
                }
            ],
            "commondb": {
                "search_permission": "approved",
                "searchable_destinations": ["useful_source", "approved_memo"],
                "source_refs": ["commondb-source:useful-source-demo"],
                "approved_memo_refs": ["commondb-memo:approved-demo"],
                "excluded_refs": ["commondb-source:unapproved-draft"],
                "migration_approval": "pending",
                "stores_raw_body": False,
            },
            "scope_guard": {
                "status": "within_spec",
                "approved_spec_ref": (
                    "artifact/workflow-ui-commondb-20260608/output/specs/"
                    "codex-app-vertical-integration-spec.md"
                ),
                "expansion_policy": "Scope expansion requires spec amendment or contract revision.",
                "completion_policy": "Completion cannot be claimed through goal drift.",
            },
            "app_server": {
                "project_id": "workflow-ui-commondb-20260608",
                "workflow_id": "codex-app-vertical-integration-20260609",
                "thread_ref": "app-server-thread:demo-thread",
                "codex_app_link_ref": "codex-app-link:workflow-ui-commondb-demo",
                "artifact_refs": [
                    "codex-app-artifact:workflow-console-html",
                    "github-pr:Dev-Foundation-ver2#19",
                ],
                "link_status": "linked",
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
