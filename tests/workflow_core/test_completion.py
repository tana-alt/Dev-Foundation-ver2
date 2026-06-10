from __future__ import annotations

import json
from pathlib import Path

from workflow_core.completion import (
    CheckOutcome,
    EvidenceRecord,
    run_completion_gate,
    write_evidence,
)

CLEAN_DIFF = "+def handler(payload):\n+    return process(payload)\n"
HACK_DIFF = "+def handler(payload):\n+    raise NotImplementedError\n"
TS = "2026-06-10T00:00:00Z"


def test_passing_check_and_clean_diff_passes() -> None:
    verdict, evidence = run_completion_gate(
        CLEAN_DIFF, "sha256:a", CheckOutcome(command="make check-required", exit_code=0), TS
    )
    assert verdict.passed is True
    assert evidence.exit_code == 0
    assert evidence.escape_patterns == []
    assert evidence.diff_hash == "sha256:a"


def test_failing_check_blocks() -> None:
    verdict, evidence = run_completion_gate(
        CLEAN_DIFF, "sha256:a", CheckOutcome(command="make check-required", exit_code=1), TS
    )
    assert verdict.passed is False
    assert "required check failed" in verdict.feedback
    assert evidence.exit_code == 1


def test_escape_blocks_even_when_check_passes() -> None:
    verdict, _ = run_completion_gate(
        HACK_DIFF, "sha256:a", CheckOutcome(command="make check-required", exit_code=0), TS
    )
    assert verdict.passed is False
    assert "escape patterns" in verdict.feedback


def test_write_evidence_roundtrip(tmp_path: Path) -> None:
    evidence = EvidenceRecord(
        command="make check-required",
        exit_code=0,
        diff_hash="sha256:abc",
        timestamp=TS,
        escape_patterns=[],
    )
    path = write_evidence(evidence, artifact_dir=tmp_path / "evidence")
    assert path.name == "check-sha256_abc.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["diff_hash"] == "sha256:abc"
    assert loaded["command"] == "make check-required"
