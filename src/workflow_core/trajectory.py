"""Trajectory recorder -- the first real harness mechanism on the runtime port.

Drives any AgentRuntime, persists the normalized trajectory as JSONL under
``artifact/<project>/trajectory/``, and returns a RunSummary the eval runner
scores from. It depends only on the port, so it records a MockRuntime or a real
Codex/Claude binding identically. No raw bodies or credentials are stored: a
TrajectoryEvent already references args by hash.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from workflow_core.contracts import StrictModel
from workflow_core.runtime import AgentRuntime, HandoffPacket, TrajectoryEvent, to_jsonl


class RunSummary(StrictModel):
    """Agent-agnostic aggregate of one run, consumed by the eval runner."""

    run_id: str
    event_count: int
    tool_calls: int
    tokens_in: int
    tokens_out: int
    tool_failures: int
    tools_used: list[str]


def summarize(run_id: str, events: Sequence[TrajectoryEvent]) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        event_count=len(events),
        tool_calls=sum(1 for event in events if event.kind == "tool_call"),
        tokens_in=sum(event.tokens_in for event in events),
        tokens_out=sum(event.tokens_out for event in events),
        tool_failures=sum(
            1 for event in events if event.exit_code is not None and event.exit_code != 0
        ),
        tools_used=sorted({event.tool for event in events if event.tool}),
    )


def record_run(
    runtime: AgentRuntime,
    packet: HandoffPacket,
    *,
    artifact_dir: Path,
) -> RunSummary:
    """Start a run, persist its trajectory JSONL, and return the summary."""
    run_id = runtime.start(packet)
    events = list(runtime.events())
    out_path = artifact_dir / f"{run_id}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = to_jsonl(events)
    out_path.write_text(f"{body}\n" if body else "", encoding="utf-8")
    return summarize(run_id, events)
