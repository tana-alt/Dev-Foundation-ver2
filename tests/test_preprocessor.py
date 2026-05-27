from pathlib import Path

import pandas as pd
import pytest

from src.preprocessor import (
    build_financial_metrics,
    calculate_surprise_pct,
    document_files_to_sections,
    safe_float,
    segment_filing,
)
from src.workflow_models import DocumentFile


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


def test_fetch_consensus_uses_yfinance_revenue_alias(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker:
        earnings_dates = pd.DataFrame(
            [{"Reported EPS": 0.81, "EPS Estimate": 0.75, "Surprise(%)": 8.0}]
        )
        quarterly_financials = pd.DataFrame([[123_000.0]], index=["Operating Revenue"])
        quarterly_cashflow = pd.DataFrame(
            [[20_000.0], [-5_000.0], [99_000.0]],
            index=["OperatingCashFlow", "Capital Expenditure", "Free Cash Flow"],
        )

        def __init__(self, ticker):
            self.ticker = ticker

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus("nvda", "2025Q3")

    assert metrics.revenue == 123_000.0
    assert metrics.operating_cash_flow == 20_000.0
    assert metrics.capex == -5_000.0
    assert metrics.free_cash_flow == 15_000.0


def test_segment_filing_extracts_semantic_sections():
    html = Path("tests/fixtures/sample_filing.html").read_text(encoding="utf-8")
    filing_url = "https://www.sec.gov/Archives/example/sample.htm"

    sections = segment_filing(html, url=filing_url)
    names = {section.heading for section in sections}

    assert {"revenue", "eps", "guidance", "segments", "risk"}.issubset(names)
    assert all(section.text for section in sections)
    assert all(section.source_ref.source_id for section in sections)
    assert all(str(section.source_ref.url) == filing_url for section in sections)


def test_document_files_to_sections_extracts_local_text_fixture():
    sections = document_files_to_sections(
        [
            DocumentFile(
                path="tests/fixtures/sample_presentation.txt",
                source_type="earnings_presentation",
                document_id="sample-presentation",
                title="Sample earnings presentation",
            )
        ]
    )

    assert len(sections) == 1
    section = sections[0]
    assert section.section_id == "sample-presentation:section-1"
    assert section.source_ref.source_id == "sample-presentation:section-1"
    assert section.source_ref.source_type == "earnings_presentation"
    assert section.source_ref.document_id == "sample-presentation"
    assert section.source_ref.section_id == "sample-presentation:section-1"
    assert section.source_ref.title == "Sample earnings presentation"
    assert "Free cash flow was pressured" in section.text


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("tests/fixtures/missing_presentation.txt", "does not exist"),
        ("tests/fixtures/sample_filing.html", "unsupported document file extension"),
    ],
)
def test_document_files_to_sections_rejects_invalid_files(path, message):
    with pytest.raises(ValueError, match=message):
        document_files_to_sections(
            [
                DocumentFile(
                    path=path,
                    source_type="earnings_presentation",
                    document_id="sample-presentation",
                    title="Sample earnings presentation",
                )
            ]
        )
