from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from workflow_core.contract_harness.domain.models import StrictModel


class Capability(StrEnum):
    READ_CONTEXT = "read_context"
    READ_STATUS = "read_status"
    SEND_ACP_MESSAGE = "send_acp_message"
    SUBMIT_CANDIDATE = "submit_candidate"
    RUN_VERIFY = "run_verify"
    RUN_REVIEW = "run_review"
    COLLECT_REVIEW = "collect_review"
    RUN_GATE = "run_gate"
    CREATE_PR = "create_pr"
    RUN_PR_CHECKS = "run_pr_checks"
    MERGE_LOCAL = "merge_local"
    COMPLETE_TASK = "complete_task"
    RECONCILE = "reconcile"
    ADMIN = "admin"


Role = Literal["writer", "reviewer", "integrator", "admin"]
SessionStatus = Literal["active", "revoked", "expired"]


class Session(StrictModel):
    schema_version: int = 1
    session_id: str
    task_id: str | None = None
    role: Role
    agent_id: str
    capabilities: list[Capability] = Field(default_factory=list)
    token_hash: str
    status: SessionStatus = "active"
    created_at: str
    expires_at: str | None = None


ROLE_CAPABILITIES: dict[str, set[Capability]] = {
    "writer": {
        Capability.READ_CONTEXT,
        Capability.READ_STATUS,
        Capability.SEND_ACP_MESSAGE,
        Capability.SUBMIT_CANDIDATE,
        Capability.RUN_VERIFY,
    },
    "reviewer": {
        Capability.READ_CONTEXT,
        Capability.READ_STATUS,
        Capability.SEND_ACP_MESSAGE,
        Capability.RUN_REVIEW,
    },
    "integrator": {
        Capability.READ_CONTEXT,
        Capability.READ_STATUS,
        Capability.SEND_ACP_MESSAGE,
        Capability.COLLECT_REVIEW,
        Capability.RUN_GATE,
        Capability.CREATE_PR,
        Capability.RUN_PR_CHECKS,
        Capability.MERGE_LOCAL,
        Capability.COMPLETE_TASK,
        Capability.RECONCILE,
    },
    "admin": set(Capability),
}


METHOD_CAPABILITIES: dict[str, Capability] = {
    "task.prepare": Capability.SUBMIT_CANDIDATE,
    "task.context": Capability.READ_CONTEXT,
    "task.status": Capability.READ_STATUS,
    "candidate.submit": Capability.SUBMIT_CANDIDATE,
    "candidate.verify": Capability.RUN_VERIFY,
    "review.run": Capability.RUN_REVIEW,
    "review.collect": Capability.COLLECT_REVIEW,
    "gate.run": Capability.RUN_GATE,
    "pr.create": Capability.CREATE_PR,
    "pr.checks": Capability.RUN_PR_CHECKS,
    "merge.local": Capability.MERGE_LOCAL,
    "task.complete": Capability.COMPLETE_TASK,
    "push.remote": Capability.COMPLETE_TASK,
    "acp.send": Capability.SEND_ACP_MESSAGE,
    "acp.list": Capability.READ_STATUS,
    "acp.request_action": Capability.READ_STATUS,
    "reconcile.task": Capability.RECONCILE,
    "outbox.resume": Capability.RECONCILE,
    "outbox.status": Capability.READ_STATUS,
    "integrity.verify": Capability.ADMIN,
}
