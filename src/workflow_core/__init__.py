"""Workflow Core state and contract helpers."""

from workflow_core.checks import WorkflowCheckError, check_workflow_document
from workflow_core.contracts import ApprovedWorkContract, WorkflowRecord
from workflow_core.evaluation import (
    EvalReport,
    EvalScore,
    ExpectedEnvelope,
    HackCase,
    aggregate,
    hack_catch_rate,
    score_run,
)
from workflow_core.gate import EscapeFinding, build_verdict, scan_escapes
from workflow_core.runtime import (
    AgentRuntime,
    GateVerdict,
    HandoffPacket,
    TrajectoryEvent,
    to_jsonl,
)
from workflow_core.trajectory import RunSummary, record_run, summarize

__all__ = [
    "AgentRuntime",
    "ApprovedWorkContract",
    "EscapeFinding",
    "EvalReport",
    "EvalScore",
    "ExpectedEnvelope",
    "GateVerdict",
    "HackCase",
    "HandoffPacket",
    "RunSummary",
    "TrajectoryEvent",
    "WorkflowCheckError",
    "WorkflowRecord",
    "aggregate",
    "build_verdict",
    "check_workflow_document",
    "hack_catch_rate",
    "record_run",
    "scan_escapes",
    "score_run",
    "summarize",
    "to_jsonl",
]
