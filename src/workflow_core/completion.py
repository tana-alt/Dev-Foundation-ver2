"""Completion gate -- the keystone (report P1): completion is decided by the
gate, not self-attested by the agent.

The gate re-derives the verdict from observed facts: the required-check exit
code and an escape scan, bound to the current diff hash. It emits an
EvidenceRecord the agent may read but never authors. ``run_completion_gate`` is
pure (the check outcome and timestamp are injected) so it is fully testable;
``scripts/completion_gate.py`` is the thin runtime entrypoint that shells out to
git and make and is meant to back a Codex/Claude stop hook.
"""

from __future__ import annotations

import json
from pathlib import Path

from workflow_core.contracts import StrictModel
from workflow_core.gate import build_verdict, scan_escapes
from workflow_core.runtime import GateVerdict


class CheckOutcome(StrictModel):
    command: str
    exit_code: int


class EvidenceRecord(StrictModel):
    """Observed evidence of a gate run. Authored by the gate, read-only to agents."""

    command: str
    exit_code: int
    diff_hash: str
    timestamp: str
    escape_patterns: list[str]


def run_completion_gate(
    diff: str,
    diff_hash: str,
    check: CheckOutcome,
    timestamp: str,
    *,
    scan_escapes_enabled: bool = True,
) -> tuple[GateVerdict, EvidenceRecord]:
    findings = scan_escapes(diff) if scan_escapes_enabled else []
    verdict = build_verdict(
        diff_hash,
        diff,
        check_passed=check.exit_code == 0,
        scan_escapes_enabled=scan_escapes_enabled,
    )
    evidence = EvidenceRecord(
        command=check.command,
        exit_code=check.exit_code,
        diff_hash=diff_hash,
        timestamp=timestamp,
        escape_patterns=sorted({finding.pattern for finding in findings}),
    )
    return verdict, evidence


def write_evidence(evidence: EvidenceRecord, *, artifact_dir: Path) -> Path:
    """Persist evidence to an agent-read-only JSON keyed by diff hash."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out = artifact_dir / f"check-{evidence.diff_hash.replace(':', '_')}.json"
    out.write_text(
        json.dumps(evidence.model_dump(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out
