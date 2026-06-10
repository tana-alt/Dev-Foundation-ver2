from __future__ import annotations

import json
from pathlib import Path

from src.workflow_adapters.mock_runtime import MockRuntime
from workflow_core.runtime import HandoffPacket, TrajectoryEvent
from workflow_core.trajectory import record_run, summarize


def event(kind: str = "tool_call", **overrides: object) -> TrajectoryEvent:
    data: dict[str, object] = {
        "ts": "2026-06-10T00:00:00Z",
        "run_id": "run-1",
        "role": "implementer",
        "kind": kind,
    }
    data.update(overrides)
    return TrajectoryEvent.model_validate(data)


def test_summarize_aggregates_calls_tokens_and_failures() -> None:
    events = [
        event(kind="tool_call", tool="pytest"),
        event(kind="tool_result", tool="pytest", exit_code=1),
        event(kind="tool_call", tool="ruff"),
        event(kind="token_usage", tokens_in=120, tokens_out=40),
    ]
    summary = summarize("run-1", events)
    assert summary.event_count == 4
    assert summary.tool_calls == 2
    assert summary.tokens_in == 120
    assert summary.tokens_out == 40
    assert summary.tool_failures == 1
    assert summary.tools_used == ["pytest", "ruff"]


def test_record_run_writes_jsonl_and_passes_packet(tmp_path: Path) -> None:
    events = [event(), event(kind="message")]
    runtime = MockRuntime(events, run_id="r42")
    packet = HandoffPacket(spec_ref="Plan/spec.md")

    summary = record_run(runtime, packet, artifact_dir=tmp_path / "trajectory")

    out_file = tmp_path / "trajectory" / "r42.jsonl"
    lines = out_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["run_id"] == "run-1" for line in lines)
    assert runtime.started_packet == packet
    assert summary.run_id == "r42"
    assert summary.event_count == 2


def test_record_run_empty_trajectory_is_empty_file(tmp_path: Path) -> None:
    runtime = MockRuntime([], run_id="empty")
    summary = record_run(runtime, HandoffPacket(spec_ref="Plan/spec.md"), artifact_dir=tmp_path)
    assert (tmp_path / "empty.jsonl").read_text(encoding="utf-8") == ""
    assert summary.event_count == 0
    assert summary.tools_used == []
