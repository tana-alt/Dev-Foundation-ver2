"""Serial-phase loop -- engaged only for spec'd work (report G8).

Running a loop on every interaction is unusable, so the loop is gated on a
present spec. Non-spec work runs a single pass. With a spec, the writer
finishing triggers review+test via ``gate``; on fail the gate feedback is sent
back as the next handoff (not full context -- the handoff is bounded), up to
``max_attempts`` attempts, then the work escalates instead of burning cycles
(failure budget, report P6).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from workflow_core.contracts import StrictModel
from workflow_core.handoff import build_handoff
from workflow_core.runtime import AgentRuntime, GateVerdict


class LoopOutcome(StrictModel):
    status: Literal["completed", "escalated", "single_pass"]
    attempts: int
    feedback: str = ""


def run_loop(
    runtime: AgentRuntime,
    spec_ref: str,
    gate: Callable[[], GateVerdict],
    *,
    spec_present: bool,
    diff: str = "",
    max_attempts: int = 3,
) -> LoopOutcome:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    if not spec_present:
        runtime.start(build_handoff(spec_ref, diff=diff))
        return LoopOutcome(status="single_pass", attempts=1)

    last_failure = ""
    for attempt in range(1, max_attempts + 1):
        runtime.start(build_handoff(spec_ref, diff=diff, last_failure=last_failure))
        verdict = gate()
        if verdict.passed:
            return LoopOutcome(status="completed", attempts=attempt)
        last_failure = verdict.feedback
        runtime.signal_block(verdict.feedback)
    return LoopOutcome(status="escalated", attempts=max_attempts, feedback=last_failure)
