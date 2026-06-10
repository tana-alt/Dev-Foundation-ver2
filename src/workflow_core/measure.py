"""Eval measurement over recorded trajectories (no SDK required).

The hook runtime records real trajectories as JSONL. This module measures them:
load a trajectory, score it against an ExpectedEnvelope, and (via the store)
accumulate structured signals while raw data ages out. Without an explicit
envelope, ``default_envelope`` whitelists everything the run actually did, so
measurement is pure counting; supply an envelope to turn on unexpected-action
detection. Success is a trajectory-local proxy (no tool-level failures), since
per-run gate correlation needs the headless drive path.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from workflow_core.evaluation import (
    SKILL_TOOL_NAMES,
    WRITE_TOOL_NAMES,
    EvalScore,
    ExpectedEnvelope,
    score_run,
)
from workflow_core.runtime import GateVerdict, TrajectoryEvent


def load_trajectory(path: Path) -> list[TrajectoryEvent]:
    return [
        TrajectoryEvent.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def default_envelope(events: Sequence[TrajectoryEvent]) -> ExpectedEnvelope:
    """Whitelist everything observed -> measurement-only (no unexpected flags)."""
    tools: set[str] = set()
    skills: set[str] = set()
    writes: set[str] = set()
    for event in events:
        if event.kind != "tool_call":
            continue
        if event.tool in SKILL_TOOL_NAMES:
            if event.target:
                skills.add(event.target)
            continue
        if event.tool:
            tools.add(event.tool)
        if event.tool in WRITE_TOOL_NAMES and event.target:
            writes.add(event.target)
    return ExpectedEnvelope(
        allowed_tools=sorted(tools),
        allowed_write_targets=sorted(writes),
        expected_skills=sorted(skills),
    )


def measure_trajectory(
    run_id: str,
    events: Sequence[TrajectoryEvent],
    envelope: ExpectedEnvelope,
) -> EvalScore:
    failures = sum(1 for event in events if event.exit_code not in (None, 0))
    verdict = GateVerdict(
        passed=failures == 0,
        diff_hash="sha256:trajectory",
        feedback="" if failures == 0 else f"{failures} tool failure(s) in trajectory",
    )
    return score_run(run_id, events, verdict, envelope)
