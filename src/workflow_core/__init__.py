"""Workflow Core state and contract helpers.

Exports are resolved lazily (PEP 562) so stdlib-only submodules such as
``workflow_core.plans`` and ``workflow_core.hook_events`` stay importable
under a plain ``python3`` without pydantic -- the hook scripts depend on
that. ``from workflow_core import X`` still works and stays typed via the
``TYPE_CHECKING`` re-exports below.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workflow_core.checks import (
        WorkflowCheckError as WorkflowCheckError,
    )
    from workflow_core.checks import (
        check_workflow_document as check_workflow_document,
    )
    from workflow_core.completion import (
        CheckOutcome as CheckOutcome,
    )
    from workflow_core.completion import (
        EvidenceRecord as EvidenceRecord,
    )
    from workflow_core.completion import (
        run_completion_gate as run_completion_gate,
    )
    from workflow_core.completion import (
        write_evidence as write_evidence,
    )
    from workflow_core.contracts import (
        ApprovedWorkContract as ApprovedWorkContract,
    )
    from workflow_core.contracts import (
        WorkflowRecord as WorkflowRecord,
    )
    from workflow_core.evaluation import (
        EvalReport as EvalReport,
    )
    from workflow_core.evaluation import (
        EvalScore as EvalScore,
    )
    from workflow_core.evaluation import (
        ExpectedEnvelope as ExpectedEnvelope,
    )
    from workflow_core.evaluation import (
        HackCase as HackCase,
    )
    from workflow_core.evaluation import (
        aggregate as aggregate,
    )
    from workflow_core.evaluation import (
        hack_catch_rate as hack_catch_rate,
    )
    from workflow_core.evaluation import (
        score_run as score_run,
    )
    from workflow_core.frozen import frozen_path_violations as frozen_path_violations
    from workflow_core.gate import (
        EscapeFinding as EscapeFinding,
    )
    from workflow_core.gate import (
        build_verdict as build_verdict,
    )
    from workflow_core.gate import (
        scan_escapes as scan_escapes,
    )
    from workflow_core.handoff import (
        build_handoff as build_handoff,
    )
    from workflow_core.handoff import (
        render_handoff as render_handoff,
    )
    from workflow_core.hook_events import from_post_tool_use as from_post_tool_use
    from workflow_core.loop import LoopOutcome as LoopOutcome
    from workflow_core.loop import run_loop as run_loop
    from workflow_core.measure import (
        default_envelope as default_envelope,
    )
    from workflow_core.measure import (
        load_trajectory as load_trajectory,
    )
    from workflow_core.measure import (
        measure_trajectory as measure_trajectory,
    )
    from workflow_core.metrics_store import MetricsStore as MetricsStore
    from workflow_core.report import (
        ResultReport as ResultReport,
    )
    from workflow_core.report import (
        build_result_report as build_result_report,
    )
    from workflow_core.runtime import (
        AgentRuntime as AgentRuntime,
    )
    from workflow_core.runtime import (
        GateVerdict as GateVerdict,
    )
    from workflow_core.runtime import (
        HandoffPacket as HandoffPacket,
    )
    from workflow_core.runtime import (
        TrajectoryEvent as TrajectoryEvent,
    )
    from workflow_core.runtime import (
        to_jsonl as to_jsonl,
    )
    from workflow_core.trajectory import (
        RunSummary as RunSummary,
    )
    from workflow_core.trajectory import (
        record_run as record_run,
    )
    from workflow_core.trajectory import (
        summarize as summarize,
    )

_EXPORTS: dict[str, str] = {
    "WorkflowCheckError": "workflow_core.checks",
    "check_workflow_document": "workflow_core.checks",
    "CheckOutcome": "workflow_core.completion",
    "EvidenceRecord": "workflow_core.completion",
    "run_completion_gate": "workflow_core.completion",
    "write_evidence": "workflow_core.completion",
    "ApprovedWorkContract": "workflow_core.contracts",
    "WorkflowRecord": "workflow_core.contracts",
    "EvalReport": "workflow_core.evaluation",
    "EvalScore": "workflow_core.evaluation",
    "ExpectedEnvelope": "workflow_core.evaluation",
    "HackCase": "workflow_core.evaluation",
    "aggregate": "workflow_core.evaluation",
    "hack_catch_rate": "workflow_core.evaluation",
    "score_run": "workflow_core.evaluation",
    "frozen_path_violations": "workflow_core.frozen",
    "EscapeFinding": "workflow_core.gate",
    "build_verdict": "workflow_core.gate",
    "scan_escapes": "workflow_core.gate",
    "build_handoff": "workflow_core.handoff",
    "render_handoff": "workflow_core.handoff",
    "from_post_tool_use": "workflow_core.hook_events",
    "LoopOutcome": "workflow_core.loop",
    "run_loop": "workflow_core.loop",
    "default_envelope": "workflow_core.measure",
    "load_trajectory": "workflow_core.measure",
    "measure_trajectory": "workflow_core.measure",
    "MetricsStore": "workflow_core.metrics_store",
    "ResultReport": "workflow_core.report",
    "build_result_report": "workflow_core.report",
    "AgentRuntime": "workflow_core.runtime",
    "GateVerdict": "workflow_core.runtime",
    "HandoffPacket": "workflow_core.runtime",
    "TrajectoryEvent": "workflow_core.runtime",
    "to_jsonl": "workflow_core.runtime",
    "RunSummary": "workflow_core.trajectory",
    "record_run": "workflow_core.trajectory",
    "summarize": "workflow_core.trajectory",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> object:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
