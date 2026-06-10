from __future__ import annotations

import pytest

from workflow_core.report import MAX_SUMMARY_CHARS, ResultReport, build_result_report


def test_valid_report() -> None:
    report = ResultReport(
        status="completed",
        summary="implemented handler and verified",
        changed_paths=["src/feature/core.py"],
        verification="make check-required: passed",
    )
    assert report.status == "completed"
    assert report.changed_paths == ["src/feature/core.py"]


def test_empty_summary_rejected() -> None:
    with pytest.raises(ValueError):
        ResultReport(status="completed", summary="   ")


def test_oversized_summary_rejected() -> None:
    with pytest.raises(ValueError):
        ResultReport(status="failed", summary="x" * (MAX_SUMMARY_CHARS + 1))


def test_build_result_report_clips_oversized_summary() -> None:
    report = build_result_report("blocked", "y" * (MAX_SUMMARY_CHARS * 2))
    assert len(report.summary) == MAX_SUMMARY_CHARS
    assert report.summary.endswith("…")


def test_build_result_report_defaults() -> None:
    report = build_result_report("completed", "  done  ")
    assert report.summary == "done"
    assert report.changed_paths == []
