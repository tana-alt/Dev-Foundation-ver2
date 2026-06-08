"""Sanitized fixture records for the local workflow console."""

from __future__ import annotations

from typing import Literal, TypedDict


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
            "runner": "mock",
            "verification_result": "skipped",
            "handoff_status": "draft",
            "external_refs": ["app-server-thread:demo-thread"],
        }
    ]
