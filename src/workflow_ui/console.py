"""Deterministic local console rendering for sanitized workflow fixtures."""

from __future__ import annotations

from collections.abc import Iterable

from src.workflow_ui.fixtures import WorkflowRun, load_sanitized_runs

FORBIDDEN_TEXT = (
    "raw_thread_body",
    "raw_terminal_log",
    "credential",
    "browser_session",
    "local_runtime_state",
)


def assert_sanitized(run: WorkflowRun) -> None:
    """Reject fixture content that would weaken the lane's evidence boundary."""
    rendered = repr(run).lower()
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in rendered:
            raise ValueError(f"fixture contains forbidden marker: {forbidden}")


def build_console_snapshot(runs: Iterable[WorkflowRun] | None = None) -> dict[str, object]:
    selected_runs = list(runs if runs is not None else load_sanitized_runs())
    for run in selected_runs:
        assert_sanitized(run)

    return {
        "screen_order": [
            "work_queue",
            "proposal_review",
            "approved_contract",
            "execution_run",
            "verification",
            "handoff",
        ],
        "runs": selected_runs,
        "real_app_server_smoke": "skipped_human_gate_required",
    }


def render_console(runs: Iterable[WorkflowRun] | None = None) -> str:
    snapshot = build_console_snapshot(runs)
    selected_runs = snapshot["runs"]
    if not isinstance(selected_runs, list):
        raise TypeError("console snapshot runs must be a list")

    lines = ["Workflow Console", "Real App Server smoke: skipped"]
    for run in selected_runs:
        lines.extend(
            [
                "",
                f"Work queue: {run['issue_id']} - {run['title']}",
                f"Proposal review: {run['proposal_summary']}",
                f"Approved contract: {run['approved_contract_ref']}",
                f"Execution run: {run['execution_status']} via {run['runner']}",
                f"Verification: {run['verification_result']}",
                f"Handoff: {run['handoff_status']}",
            ]
        )
    return "\n".join(lines)
