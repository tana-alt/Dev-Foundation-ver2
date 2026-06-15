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


# ---------------------------------------------------------------------------
# build_verdict with precomputed findings
# ---------------------------------------------------------------------------


def test_build_verdict_precomputed_empty_findings_overrides_scan() -> None:
    """Explicit findings=[] skips the rescan even when escape patterns exist in the diff."""
    from workflow_core.gate import build_verdict

    diff_with_escape = "+    raise NotImplementedError\n"
    # If findings=[] is respected (no rescan), the verdict should pass.
    verdict = build_verdict(
        "sha256:test",
        diff_with_escape,
        check_passed=True,
        scan_escapes_enabled=True,
        findings=[],
    )
    assert verdict.passed is True


def test_build_verdict_precomputed_findings_equal_direct_scan() -> None:
    """Precomputed findings from scan_escapes() must yield the same verdict as an internal scan."""
    from workflow_core.gate import build_verdict, scan_escapes

    diff = "+    raise NotImplementedError\n+x = 1\n"
    precomputed = scan_escapes(diff)
    assert precomputed  # sanity: there is a finding

    verdict_precomputed = build_verdict(
        "sha256:test",
        diff,
        check_passed=True,
        scan_escapes_enabled=True,
        findings=precomputed,
    )
    verdict_internal = build_verdict(
        "sha256:test",
        diff,
        check_passed=True,
        scan_escapes_enabled=True,
        findings=None,
    )
    assert verdict_precomputed.passed == verdict_internal.passed
    assert verdict_precomputed.feedback == verdict_internal.feedback
