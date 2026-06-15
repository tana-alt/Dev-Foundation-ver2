from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow_core.tracelog import TraceWriter

# ---------------------------------------------------------------------------
# emit
# ---------------------------------------------------------------------------


def test_emit_writes_r14_envelope(tmp_path: Path) -> None:
    path = tmp_path / "trace" / "sess.jsonl"
    writer = TraceWriter(path, session_id="sess_1", actor="abrun")
    envelope = writer.emit("metric_recorded", {"metric": "m", "value": 1.0}, {"run_id": "cand_001"})
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed == envelope
    assert parsed["session_id"] == "sess_1"
    assert parsed["actor"] == "abrun"
    assert parsed["seq"] == 1
    assert parsed["event"] == "metric_recorded"
    assert parsed["refs"] == {"run_id": "cand_001"}
    assert "ts" in parsed


def test_seq_increments_and_resumes(tmp_path: Path) -> None:
    path = tmp_path / "sess.jsonl"
    first = TraceWriter(path, session_id="s", actor="a")
    first.emit("decision")
    first.emit("command")
    resumed = TraceWriter(path, session_id="s", actor="b")
    envelope = resumed.emit("gate_result")
    assert envelope["seq"] == 3
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_unknown_event_rejected(tmp_path: Path) -> None:
    writer = TraceWriter(tmp_path / "t.jsonl", session_id="s", actor="a")
    with pytest.raises(ValueError, match="unknown trace event"):
        writer.emit("not_an_event")
