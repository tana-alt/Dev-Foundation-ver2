from typing import Any

import pytest

from workflow_core.checks import WorkflowCheckError, check_execution_ready, check_transition
from workflow_core.contracts import WorkflowStatus


def valid_contract() -> dict[str, Any]:
    return {
        "work_contract_id": "work-001",
        "issue_id": "issue-001",
        "proposal_id": "proposal-001",
        "project_id": "project-001",
        "goal": "Implement the approved task.",
        "source_refs": ["AGENTS.md"],
        "allowed_write_targets": ["src/**"],
        "denied_context": ["secrets", "runtime_state"],
        "verification": ["make test"],
        "human_gate": {"status": "approved", "approved_by": "", "evidence_ref": ""},
        "risk_flags": [],
        "git_scope": {
            "mode": "parallel",
            "base_ref": "origin/main",
            "merge_target": "origin/main",
            "branch_target": "agent/work-001/impl/task",
            "worktree_target": "../worktrees/repo/work-001-impl",
            "sibling_branch_refs": [],
            "conflict_policy": "no_overlap",
        },
    }


def execution_record(status: str = "approved_work_contract") -> dict[str, object]:
    return {
        "record_type": "execution_run",
        "status": status,
        "approval": {"status": "approved"},
        "approved_work_contract": valid_contract(),
    }


def test_valid_transition_to_execution_run() -> None:
    check_transition("approved_work_contract", "execution_run")


def test_invalid_transition_skips_approval() -> None:
    with pytest.raises(WorkflowCheckError, match="invalid workflow transition"):
        check_transition("implementation_proposal", "execution_run")


@pytest.mark.parametrize(
    "status",
    [
        WorkflowStatus.CHANGES_REQUESTED.value,
        WorkflowStatus.BLOCKED.value,
        WorkflowStatus.REJECTED.value,
    ],
)
def test_execution_rejects_blocking_statuses(status: str) -> None:
    with pytest.raises(WorkflowCheckError, match="execution is blocked"):
        check_execution_ready(execution_record(status))


def test_execution_requires_approval() -> None:
    record = execution_record()
    record["approval"] = {"status": "required"}

    with pytest.raises(WorkflowCheckError, match="requires an approved"):
        check_execution_ready(record)


def test_execution_requires_contract_boundaries() -> None:
    record = execution_record()
    contract = valid_contract()
    contract["source_refs"] = []
    record["approved_work_contract"] = contract

    with pytest.raises(ValueError, match="source_refs"):
        check_execution_ready(record)
