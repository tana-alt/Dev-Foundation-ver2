"""Agent-agnostic harness seam.

This module is the single rail every agent runtime (Codex, Claude, future
runtimes) must bind through. It defines:

- the normalized vocabulary the whole harness speaks (TrajectoryEvent,
  HandoffPacket, GateVerdict), and
- the AgentRuntime port that adapters implement.

workflow_core must never import a concrete runtime. Runtime-native event
translation lives in workflow_adapters behind this port. Enforcement of that
boundary is mechanical (see tests/workflow_core/test_runtime_port.py).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import model_validator

from workflow_core.contracts import StrictModel

EventKind = Literal["tool_call", "tool_result", "message", "token_usage"]


class TrajectoryEvent(StrictModel):
    """One normalized step of an agent run.

    Adapters map a runtime-native event onto this shape. Raw bodies, terminal
    logs, and credentials are never stored here; the full payload is referenced
    by ``args_hash``. ``target`` carries only a bounded identifier the action
    acts on -- a write path, skill name, or command name -- so eval can detect
    out-of-envelope writes and skill usage without storing content.
    """

    ts: str
    run_id: str
    role: str
    kind: EventKind
    tool: str = ""
    target: str = ""
    args_hash: str = ""
    exit_code: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0

    @model_validator(mode="after")
    def identity_is_present(self) -> Self:
        for name in ("ts", "run_id", "role"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        return self


class HandoffPacket(StrictModel):
    """The only bounded input an agent turn receives into its context.

    Carries the frozen spec reference, the current diff, and the last gate
    failure -- not full conversation history. This is both the context-budget
    mechanism and the loop's hand-off organ.
    """

    spec_ref: str
    diff: str = ""
    last_failure: str = ""

    @model_validator(mode="after")
    def spec_ref_is_present(self) -> Self:
        if not self.spec_ref.strip():
            raise ValueError("spec_ref must be non-empty")
        return self


class GateVerdict(StrictModel):
    """The completion gate's verdict, bound to a specific diff hash."""

    passed: bool
    diff_hash: str
    feedback: str = ""

    @model_validator(mode="after")
    def failed_verdict_explains(self) -> Self:
        if not self.passed and not self.feedback.strip():
            raise ValueError("a failed verdict must carry feedback")
        return self


@runtime_checkable
class AgentRuntime(Protocol):
    """The seam every concrete agent runtime binds through.

    Implementations live in workflow_adapters and translate runtime-native
    events into TrajectoryEvent. The gate, trajectory recorder, handoff
    builder, and eval runner depend only on this port, so they stay agent
    agnostic and can be developed against MockRuntime without a real agent.
    """

    def start(self, packet: HandoffPacket) -> str:
        """Begin an agent turn from the bounded packet; return a run id."""
        ...

    def events(self) -> Iterable[TrajectoryEvent]:
        """Yield the run's normalized trajectory."""
        ...

    def signal_block(self, feedback: str) -> None:
        """Refuse completion and hand bounded feedback back to the runtime."""
        ...


def to_jsonl(events: Sequence[TrajectoryEvent]) -> str:
    """Serialize a normalized trajectory to JSONL (agent-agnostic persistence)."""
    return "\n".join(json.dumps(event.model_dump(), sort_keys=True) for event in events)
