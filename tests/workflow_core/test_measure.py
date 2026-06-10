from __future__ import annotations

from pathlib import Path

from workflow_core.evaluation import ExpectedEnvelope
from workflow_core.measure import default_envelope, load_trajectory, measure_trajectory
from workflow_core.runtime import TrajectoryEvent, to_jsonl


def event(kind: str = "tool_call", **overrides: object) -> TrajectoryEvent:
    data: dict[str, object] = {
        "ts": "2026-06-11T00:00:00Z",
        "run_id": "sess",
        "role": "implementer",
        "kind": kind,
    }
    data.update(overrides)
    return TrajectoryEvent.model_validate(data)


def test_load_trajectory_roundtrips(tmp_path: Path) -> None:
    events = [event(tool="Edit", target="src/feature/core.py"), event(kind="message")]
    path = tmp_path / "sess.jsonl"
    path.write_text(to_jsonl(events) + "\n", encoding="utf-8")
    loaded = load_trajectory(path)
    assert loaded == events


def test_default_envelope_whitelists_everything_observed() -> None:
    events = [
        event(tool="Edit", target="src/x.py"),
        event(tool="WebFetch"),
        event(tool="Skill", target="code-review"),
    ]
    envelope = default_envelope(events)
    assert envelope.allowed_tools == ["Edit", "WebFetch"]
    assert envelope.allowed_write_targets == ["src/x.py"]
    assert envelope.expected_skills == ["code-review"]
    # measured against its own default -> nothing unexpected
    score = measure_trajectory("sess", events, envelope)
    assert score.unexpected_actions == []


def test_measure_flags_unexpected_against_explicit_envelope() -> None:
    events = [event(tool="WebFetch"), event(tool="Edit", target="src/secret.py")]
    envelope = ExpectedEnvelope(allowed_tools=["Read"], allowed_write_targets=["src/feature/"])
    score = measure_trajectory("sess", events, envelope)
    assert "unexpected tool: WebFetch" in score.unexpected_actions
    assert "write outside targets: src/secret.py" in score.unexpected_actions


def test_tool_failure_marks_run_unsuccessful() -> None:
    events = [event(kind="tool_result", tool="Bash", exit_code=1)]
    score = measure_trajectory("sess", events, default_envelope(events))
    assert score.succeeded is False
