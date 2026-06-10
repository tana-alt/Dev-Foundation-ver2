"""Workflow Core state and contract helpers."""

from workflow_core.checks import WorkflowCheckError, check_workflow_document
from workflow_core.completion import (
    CheckOutcome,
    EvidenceRecord,
    run_completion_gate,
    write_evidence,
)
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
from workflow_core.frozen import frozen_path_violations
from workflow_core.gate import EscapeFinding, build_verdict, scan_escapes
from workflow_core.handoff import build_handoff, render_handoff
from workflow_core.hook_events import from_post_tool_use
from workflow_core.loop import LoopOutcome, run_loop
from workflow_core.metrics_store import MetricsStore
from workflow_core.report import ResultReport, build_result_report
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
    "CheckOutcome",
    "EscapeFinding",
    "EvalReport",
    "EvalScore",
    "EvidenceRecord",
    "ExpectedEnvelope",
    "GateVerdict",
    "HackCase",
    "HandoffPacket",
    "LoopOutcome",
    "MetricsStore",
    "ResultReport",
    "RunSummary",
    "TrajectoryEvent",
    "WorkflowCheckError",
    "WorkflowRecord",
    "aggregate",
    "build_handoff",
    "build_result_report",
    "build_verdict",
    "check_workflow_document",
    "frozen_path_violations",
    "from_post_tool_use",
    "hack_catch_rate",
    "record_run",
    "render_handoff",
    "run_completion_gate",
    "run_loop",
    "scan_escapes",
    "score_run",
    "summarize",
    "to_jsonl",
    "write_evidence",
]
