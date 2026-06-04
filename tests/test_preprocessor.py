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
    metric_store = {(entry.metric_name, entry.period_role): entry for entry in metrics.metric_store}
    assert metric_store[("eps", "reported_period_actuals")].value == 0.81
    assert metric_store[("eps_consensus", "consensus_for_reported_period")].value == 0.75
    assert all(entry.source_name for entry in metrics.metric_store)


def test_fetch_consensus_uses_yfinance_revenue_alias(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker:
        earnings_dates = pd.DataFrame(
            [{"Reported EPS": 0.81, "EPS Estimate": 0.75, "Surprise(%)": 8.0}],
            index=pd.to_datetime(["2025-11-19"]),
        )
        quarterly_financials = pd.DataFrame(
            [[123_000.0]],
            index=["Operating Revenue"],
            columns=pd.to_datetime(["2025-10-31"]),
        )
        quarterly_cashflow = pd.DataFrame(
            [[20_000.0], [-5_000.0], [99_000.0]],
            index=["OperatingCashFlow", "Capital Expenditure", "Free Cash Flow"],
            columns=pd.to_datetime(["2025-10-31"]),
        )

        def __init__(self, ticker):
            self.ticker = ticker

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus(
        "nvda",
        "2025Q3",
        target_earnings_date="2025-11-19",
        target_period_end_date="2025-10-31",
    )

    assert metrics.revenue == 123_000.0
    assert metrics.operating_cash_flow == 20_000.0
    assert metrics.capex == -5_000.0
    assert metrics.free_cash_flow == 15_000.0


class _FakeTickerBase:
    quarterly_financials = pd.DataFrame()
    quarterly_cashflow = pd.DataFrame()

    def __init__(self, ticker: str):
        self.ticker = ticker


def test_fetch_consensus_selects_target_earnings_date_not_future_first_row(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker(_FakeTickerBase):
        earnings_dates = pd.DataFrame(
            [
                {"Reported EPS": None, "EPS Estimate": 0.95, "Surprise(%)": None},
                {"Reported EPS": 0.81, "EPS Estimate": 0.75, "Surprise(%)": 8.0},
                {"Reported EPS": 0.73, "EPS Estimate": 0.70, "Surprise(%)": 4.29},
            ],
            index=pd.to_datetime(["2026-02-18", "2025-11-19", "2025-08-27"]),
        )

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus(
        "nvda",
        "2025Q3",
        target_earnings_date="2025-11-19",
    )

    assert metrics.eps == 0.81
    assert metrics.eps_consensus == 0.75
    assert metrics.eps_surprise_pct == 8.0
    assert metrics.source_row_date.isoformat() == "2025-11-19"
    assert "reported_period_actuals" in metrics.temporal_snapshots
    assert metrics.temporal_snapshots["pre_earnings_consensus"]["metrics"]["eps_consensus"] == 0.75
    roles = {entry.period_role for entry in metrics.metric_store}
    assert "reported_period_actuals" in roles
    assert "consensus_for_reported_period" in roles
    assert "pre_earnings_consensus" not in roles


def test_fetch_consensus_missing_target_row_returns_missing_eps_not_future_values(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker(_FakeTickerBase):
        earnings_dates = pd.DataFrame(
            [{"Reported EPS": None, "EPS Estimate": 0.95, "Surprise(%)": None}],
            index=pd.to_datetime(["2026-02-18"]),
        )

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus(
        "nvda",
        "2025Q3",
        target_earnings_date="2025-11-19",
    )

    assert metrics.eps is None
    assert metrics.eps_consensus is None
    assert metrics.eps_surprise_pct is None
    assert metrics.source_row_date is None
    assert metrics.warnings


def test_fetch_consensus_respects_financial_data_cutoff_before_earnings(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker(_FakeTickerBase):
        earnings_dates = pd.DataFrame(
            [{"Reported EPS": 0.81, "EPS Estimate": 0.75, "Surprise(%)": 8.0}],
            index=pd.to_datetime(["2025-11-19"]),
        )
        quarterly_financials = pd.DataFrame(
            [[35_000.0]],
            index=["Operating Revenue"],
            columns=pd.to_datetime(["2025-10-31"]),
        )

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus(
        "nvda",
        "2025Q3",
        target_earnings_date="2025-11-19",
        target_period_end_date="2025-10-31",
        financial_data_as_of="2025-11-18",
    )

    assert metrics.eps is None
    assert metrics.revenue is None
    assert metrics.warnings


def test_fetch_consensus_selects_target_and_prior_pnl_columns_by_period_end(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker(_FakeTickerBase):
        earnings_dates = pd.DataFrame(
            [{"Reported EPS": 0.81, "EPS Estimate": 0.75, "Surprise(%)": 8.0}],
            index=pd.to_datetime(["2025-11-19"]),
        )
        quarterly_financials = pd.DataFrame(
            [[35_000.0, 30_000.0]],
            index=["Operating Revenue"],
            columns=pd.to_datetime(["2025-10-31", "2025-07-31"]),
        )
        quarterly_cashflow = pd.DataFrame(
            [[15_000.0, 12_000.0], [-3_000.0, -2_000.0], [12_000.0, 10_000.0]],
            index=["OperatingCashFlow", "Capital Expenditure", "Free Cash Flow"],
            columns=pd.to_datetime(["2025-10-31", "2025-07-31"]),
        )

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    metrics = fetch_consensus(
        "nvda",
        "2025Q3",
        target_earnings_date="2025-11-19",
        target_period_end_date="2025-10-31",
        prior_fiscal_period="2025Q2",
    )

    assert metrics.revenue == 35_000.0
    assert metrics.operating_cash_flow == 15_000.0
    assert metrics.capex == -3_000.0
    assert metrics.free_cash_flow == 12_000.0
    assert metrics.source_table_column_date.isoformat() == "2025-10-31"
    prior = metrics.temporal_snapshots["prior_sequential_period_actuals"]
    assert prior["bucket"] == "prior_sequential_period_actuals"
    assert prior["fiscal_period"] == "2025Q2"
    assert prior["source_table_column_date"] == "2025-07-31"
    assert prior["metrics"]["revenue"] == 30_000.0
    roles = {entry.period_role for entry in metrics.metric_store}
    assert "prior_sequential_period_actuals" in roles
    assert "prior_year_period" not in {entry.period_role for entry in metrics.metric_store}


def test_fetch_consensus_rejects_non_sequential_prior_fiscal_period(monkeypatch):
    from src.preprocessor import fetch_consensus

    class FakeTicker(_FakeTickerBase):
        earnings_dates = pd.DataFrame()

    monkeypatch.setattr("src.preprocessor.yf.Ticker", FakeTicker)

    with pytest.raises(ValueError, match="prior_fiscal_period"):
        fetch_consensus(
            "nvda",
            "2025Q1",
            target_earnings_date="2025-05-20",
            prior_fiscal_period="2024Q3",
        )


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
