from __future__ import annotations

import pytest

from src.workflow_adapters.mock_runtime import MockRuntime
from workflow_core.loop import run_loop
from workflow_core.runtime import GateVerdict


def passing() -> GateVerdict:
    return GateVerdict(passed=True, diff_hash="sha256:a")


def failing() -> GateVerdict:
    return GateVerdict(passed=False, diff_hash="sha256:b", feedback="check failed")


def test_non_spec_work_runs_single_pass_without_loop() -> None:
    runtime = MockRuntime([])
    outcome = run_loop(runtime, "goal-only", passing, spec_present=False)
    assert outcome.status == "single_pass"
    assert outcome.attempts == 1
    assert runtime.block_feedback == []


def test_spec_work_completes_on_first_pass() -> None:
    runtime = MockRuntime([])
    outcome = run_loop(runtime, "Plan/spec.md", passing, spec_present=True)
    assert outcome.status == "completed"
    assert outcome.attempts == 1


def test_spec_work_loops_until_gate_passes() -> None:
    verdicts = [failing(), failing(), passing()]
    runtime = MockRuntime([])
    outcome = run_loop(runtime, "Plan/spec.md", lambda: verdicts.pop(0), spec_present=True)
    assert outcome.status == "completed"
    assert outcome.attempts == 3
    assert runtime.block_feedback == ["check failed", "check failed"]


def test_spec_work_escalates_after_budget() -> None:
    runtime = MockRuntime([])
    outcome = run_loop(runtime, "Plan/spec.md", failing, spec_present=True, max_attempts=2)
    assert outcome.status == "escalated"
    assert outcome.attempts == 2
    assert outcome.feedback == "check failed"
    assert len(runtime.block_feedback) == 2


def test_invalid_budget_rejected() -> None:
    with pytest.raises(ValueError):
        run_loop(MockRuntime([]), "Plan/spec.md", passing, spec_present=True, max_attempts=0)
