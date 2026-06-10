"""Script-driven AgentRuntime for building the harness without a real agent.

Satisfies workflow_core.runtime.AgentRuntime structurally. The completion gate,
trajectory recorder, handoff builder, and eval runner are all developed and
tested against this -- no Codex or Claude process required. The real bindings
(Codex SDK / app-server, Claude hooks) are thin adapters that satisfy the same
port; nothing downstream depends on which runtime is behind it.
"""

from __future__ import annotations

from collections.abc import Iterable

from workflow_core.runtime import HandoffPacket, TrajectoryEvent


class MockRuntime:
    def __init__(self, script: Iterable[TrajectoryEvent], run_id: str = "mock-run") -> None:
        self._script: list[TrajectoryEvent] = list(script)
        self._run_id = run_id
        self.started_packet: HandoffPacket | None = None
        self.block_feedback: list[str] = []

    def start(self, packet: HandoffPacket) -> str:
        self.started_packet = packet
        return self._run_id

    def events(self) -> Iterable[TrajectoryEvent]:
        yield from self._script

    def signal_block(self, feedback: str) -> None:
        self.block_feedback.append(feedback)
