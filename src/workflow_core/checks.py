from __future__ import annotations

from typing import Any

from workflow_core.contracts import ApprovedWorkContract, WorkflowStatus, can_transition


class WorkflowCheckError(ValueError):
    """Raised when workflow records are unsafe for the next adapter step."""


BLOCKING_EXECUTION_STATUSES = {
    WorkflowStatus.CHANGES_REQUESTED,
    WorkflowStatus.BLOCKED,
    WorkflowStatus.REJECTED,
}


def check_transition(current_status: str, next_status: str) -> None:
    current = WorkflowStatus(current_status)
    next_value = WorkflowStatus(next_status)
    if not can_transition(current, next_value):
        raise WorkflowCheckError(f"invalid workflow transition: {current} -> {next_value}")


def check_execution_ready(record: dict[str, Any]) -> None:
    status = WorkflowStatus(str(record.get("status", "")))
    if status in BLOCKING_EXECUTION_STATUSES:
        raise WorkflowCheckError(f"execution is blocked by status: {status}")

    approval = record.get("approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        raise WorkflowCheckError("execution requires an approved approval decision")

    contract_data = record.get("approved_work_contract")
    if not isinstance(contract_data, dict):
        raise WorkflowCheckError("execution requires approved_work_contract data")
    ApprovedWorkContract.model_validate(contract_data)


def check_workflow_document(document: dict[str, Any]) -> None:
    if "transition" in document:
        transition = document["transition"]
        if not isinstance(transition, dict):
            raise WorkflowCheckError("transition must be a mapping")
        check_transition(str(transition.get("from", "")), str(transition.get("to", "")))

    if document.get("record_type") == "execution_run" or document.get("intent") == "execute":
        check_execution_ready(document)
