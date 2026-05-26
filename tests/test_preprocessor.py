from pathlib import Path

import pytest

from src.preprocessor import (
    build_earnings_context,
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


def test_build_earnings_context_computes_eps_surprise():
    ctx = build_earnings_context(
        ticker="nvda",
        quarter="2025Q3",
        eps_actual=0.81,
        eps_consensus=0.75,
    )

    assert ctx.ticker == "NVDA"
    assert round(ctx.eps_surprise_pct or 0, 2) == 8.0


def test_segment_filing_extracts_semantic_sections():
    html = Path("tests/fixtures/sample_filing.html").read_text(encoding="utf-8")

    sections = segment_filing(html)
    names = {section.name for section in sections}

    assert {"revenue", "eps", "guidance", "segments", "risk"}.issubset(names)
    assert all(section.text for section in sections)
