from __future__ import annotations

from pathlib import Path

import pytest

from src.workflow_adapters.mock_runtime import MockRuntime
from workflow_core.runtime import (
    AgentRuntime,
    GateVerdict,
    HandoffPacket,
    TrajectoryEvent,
    to_jsonl,
)

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "workflow_core"
FORBIDDEN_IMPORT_TOKENS = ("codex", "claude", "workflow_adapters", "workflow_ui")


def sample_event(kind: str = "tool_call", **overrides: object) -> TrajectoryEvent:
    data: dict[str, object] = {
        "ts": "2026-06-10T00:00:00Z",
        "run_id": "run-1",
        "role": "implementer",
        "kind": kind,
    }
    data.update(overrides)
    return TrajectoryEvent.model_validate(data)


def test_mock_runtime_satisfies_port() -> None:
    runtime = MockRuntime([sample_event()])
    assert isinstance(runtime, AgentRuntime)


def test_start_records_packet_and_events_replay_script() -> None:
    events = [sample_event(), sample_event(kind="token_usage", tokens_in=10, tokens_out=5)]
    runtime = MockRuntime(events, run_id="r9")
    packet = HandoffPacket(spec_ref="Plan/spec.md")
    assert runtime.start(packet) == "r9"
    assert runtime.started_packet == packet
    assert list(runtime.events()) == events


def test_signal_block_accumulates_feedback() -> None:
    runtime = MockRuntime([])
    runtime.signal_block("required check did not pass")
    assert runtime.block_feedback == ["required check did not pass"]


def test_trajectory_serializes_to_jsonl() -> None:
    lines = to_jsonl([sample_event(), sample_event(kind="message")]).splitlines()
    assert len(lines) == 2


def test_failed_verdict_requires_feedback() -> None:
    with pytest.raises(ValueError):
        GateVerdict(passed=False, diff_hash="sha256:x")
    GateVerdict(passed=True, diff_hash="sha256:x")


def test_event_identity_required() -> None:
    with pytest.raises(ValueError):
        sample_event(run_id="  ")


def test_handoff_requires_spec_ref() -> None:
    with pytest.raises(ValueError):
        HandoffPacket(spec_ref="")


def test_workflow_core_stays_runtime_agnostic() -> None:
    """The rail itself: core must never import a concrete agent runtime."""
    offenders: list[str] = []
    for path in sorted(CORE_DIR.glob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lower()
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if any(token in stripped for token in FORBIDDEN_IMPORT_TOKENS):
                offenders.append(f"{path.name}: {line.strip()}")
    assert not offenders, f"workflow_core must stay runtime-agnostic: {offenders}"
