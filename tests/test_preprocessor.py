from pathlib import Path

import pytest

from src.preprocessor import (
    build_financial_metrics,
    calculate_surprise_pct,
    safe_float,
    segment_filing,
)


def test_safe_float_discards_invalid_external_values():
    assert safe_float("1.25") == 1.25
    assert safe_float(None) is None
    assert safe_float("not-a-number") is None
    assert safe_float(float("nan")) is None


def test_calculate_surprise_pct_handles_missing_consensus():
    assert calculate_surprise_pct(0.81, 0.75) == pytest.approx(8.0)
    assert calculate_surprise_pct(0.81, None) is None
    assert calculate_surprise_pct(0.81, 0) is None


def test_build_financial_metrics_computes_eps_surprise():
    metrics = build_financial_metrics(
        ticker="nvda",
        fiscal_period="2025Q3",
        eps=0.81,
        eps_consensus=0.75,
    )

    assert metrics.ticker == "NVDA"
    assert round(metrics.eps_surprise_pct or 0, 2) == 8.0


def test_segment_filing_extracts_semantic_sections():
    html = Path("tests/fixtures/sample_filing.html").read_text(encoding="utf-8")

    sections = segment_filing(html)
    names = {section.heading for section in sections}

    assert {"revenue", "eps", "guidance", "segments", "risk"}.issubset(names)
    assert all(section.text for section in sections)
    assert all(section.source_ref.source_id for section in sections)
