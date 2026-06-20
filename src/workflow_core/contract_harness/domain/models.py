from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowPhase(StrEnum):
    DEFINED = "defined"
    PREPARED = "prepared"
    WRITER_ACTIVE = "writer_active"
    VERIFIED = "verified"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"
    GATED = "gated"
    PR_CREATED = "pr_created"
    PR_CHECKED = "pr_checked"
    INTEGRATED = "integrated"
    LANDED = "landed"
    PUSHED = "pushed"
    COMPLETE = "complete"
    REWORK_REQUIRED = "rework_required"
    BLOCKED = "blocked"
    INCONSISTENT = "inconsistent"
    UNKNOWN = "unknown"


class ArtifactRef(StrictModel):
    sha256: str
    media_type: str
    size_bytes: int
    storage_uri: str


class StateEvent(StrictModel):
    id: int | None = None
    task_id: str
    candidate_id: str | None = None
    event_type: str
    from_phase: WorkflowPhase | None = None
    to_phase: WorkflowPhase
    payload_json: str
    payload_sha256: str
    previous_event_sha256: str | None = None
    event_sha256: str
    actor: str
    created_at: str


class ImpactFinding(StrictModel):
    path: str
    severity: Literal["info", "warning", "block"]
    reason: str


class ImpactResult(StrictModel):
    status: Literal["ok", "review_required", "blocked"]
    findings: list[ImpactFinding] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    expected_paths: list[str] = Field(default_factory=list)
    forbidden_paths: list[str] = Field(default_factory=list)


class VerifierResult(StrictModel):
    id: str
    status: Literal["pass", "fail", "timeout", "error"]
    exit_code: int
    duration_ms: int
    stdout_sha256: str | None = None
    stderr_sha256: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    timed_out: bool = False


class ReviewSummary(StrictModel):
    quorum: int
    fresh_approves: int
    fresh_blocks: int
    fresh_reviewers: list[str]
    blocking_reviewers: list[str]
    review_pass: bool


class EventAppend(StrictModel):
    task_id: str
    candidate_id: str | None = None
    event_type: str
    from_phase: WorkflowPhase | None = None
    to_phase: WorkflowPhase
    payload: dict[str, Any]
    actor: str = "harness"
