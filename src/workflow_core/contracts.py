from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowStatus(StrEnum):
    ISSUE_CANDIDATE = "issue_candidate"
    ISSUE = "issue"
    IMPLEMENTATION_PROPOSAL = "implementation_proposal"
    APPROVAL_DECISION = "approval_decision"
    APPROVED_WORK_CONTRACT = "approved_work_contract"
    EXECUTION_RUN = "execution_run"
    VERIFICATION_RESULT = "verification_result"
    HANDOFF_ARTIFACT = "handoff_artifact"
    BLOCKED = "blocked"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def validate_execution_boundaries(
    *,
    goal: str,
    source_refs: Sequence[str],
    allowed_write_targets: Sequence[str],
    verification: Sequence[str],
) -> None:
    required_lists = {
        "source_refs": source_refs,
        "allowed_write_targets": allowed_write_targets,
        "verification": verification,
    }
    for field_name, values in required_lists.items():
        if not values or any(not value.strip() for value in values):
            raise ValueError(f"{field_name} must be a non-empty string list")
    if not goal.strip():
        raise ValueError("goal must be non-empty")


class GitScope(StrictModel):
    mode: Literal["single", "parallel"]
    base_ref: str
    merge_target: str
    branch_target: str
    worktree_target: str
    sibling_branch_refs: list[str] = Field(default_factory=list)
    conflict_policy: Literal["no_overlap", "report_overlap", "explicitly_scoped"]


class HumanGate(StrictModel):
    status: Literal["required", "approved", "blocked", "not_applicable"]
    approved_by: str = ""
    evidence_ref: str = ""


class ApprovedWorkContract(StrictModel):
    work_contract_id: str
    issue_id: str
    proposal_id: str
    project_id: str
    goal: str
    source_refs: list[str]
    allowed_write_targets: list[str]
    denied_context: list[str]
    verification: list[str]
    human_gate: HumanGate
    risk_flags: list[str] = Field(default_factory=list)
    git_scope: GitScope

    @model_validator(mode="after")
    def required_execution_boundaries_are_present(self) -> Self:
        validate_execution_boundaries(
            goal=self.goal,
            source_refs=self.source_refs,
            allowed_write_targets=self.allowed_write_targets,
            verification=self.verification,
        )
        return self


class WorkflowRecord(StrictModel):
    record_type: Literal[
        "issue_candidate",
        "issue",
        "implementation_proposal",
        "approval_decision",
        "approved_work_contract",
        "execution_run",
        "verification_result",
        "handoff_artifact",
    ]
    status: WorkflowStatus
    identity: dict[str, str]
    refs: dict[str, Any] = Field(default_factory=dict)
    approval: dict[str, Any] = Field(default_factory=dict)
    approved_work_contract: ApprovedWorkContract | None = None


ALLOWED_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.ISSUE_CANDIDATE: {WorkflowStatus.ISSUE, WorkflowStatus.REJECTED},
    WorkflowStatus.ISSUE: {
        WorkflowStatus.IMPLEMENTATION_PROPOSAL,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.IMPLEMENTATION_PROPOSAL: {
        WorkflowStatus.APPROVAL_DECISION,
        WorkflowStatus.CHANGES_REQUESTED,
        WorkflowStatus.REJECTED,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.APPROVAL_DECISION: {
        WorkflowStatus.APPROVED_WORK_CONTRACT,
        WorkflowStatus.CHANGES_REQUESTED,
        WorkflowStatus.REJECTED,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.APPROVED_WORK_CONTRACT: {
        WorkflowStatus.EXECUTION_RUN,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.EXECUTION_RUN: {
        WorkflowStatus.VERIFICATION_RESULT,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.VERIFICATION_RESULT: {
        WorkflowStatus.HANDOFF_ARTIFACT,
        WorkflowStatus.CHANGES_REQUESTED,
        WorkflowStatus.BLOCKED,
    },
    WorkflowStatus.HANDOFF_ARTIFACT: set(),
    WorkflowStatus.BLOCKED: set(),
    WorkflowStatus.REJECTED: set(),
    WorkflowStatus.CHANGES_REQUESTED: {WorkflowStatus.IMPLEMENTATION_PROPOSAL},
}


def can_transition(current: WorkflowStatus, next_status: WorkflowStatus) -> bool:
    return next_status in ALLOWED_TRANSITIONS[current]
