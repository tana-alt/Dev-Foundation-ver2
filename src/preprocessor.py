"""Preprocessor: fetches filing + market consensus, then segments the
filing into typed sections.

This module is THE answer to context engineering: the LLM never sees
the raw 80-page filing. By the time anything reaches an agent, it has
been (a) chunked semantically and (b) annotated with structured numbers.
"""
from __future__ import annotations

import os
import re
from math import isfinite
from pathlib import Path
from typing import Any

import structlog
import yfinance as yf
from bs4 import BeautifulSoup

from .workflow_models import DocumentSection, FinancialMetrics, SourceRef, SourceType

log = structlog.get_logger()


SECTION_PATTERNS = {
    "revenue":  re.compile(r"(net\s+revenue|total\s+revenue|net\s+sales)", re.I),
    "eps":      re.compile(r"(earnings\s+per\s+share|diluted\s+eps)", re.I),
    "guidance": re.compile(r"(outlook|guidance)", re.I),
    "segments": re.compile(r"(segment|geographic|product\s+category)", re.I),
    "risk":     re.compile(r"(risk\s+factor|forward[- ]looking\s+statement)", re.I),
}


def safe_float(value: Any) -> float | None:
    """Convert external numeric values without leaking NaN into contracts."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def calculate_surprise_pct(actual: float | None, consensus: float | None) -> float | None:
    if actual is None or consensus is None or consensus == 0:
        return None
    return ((actual - consensus) / abs(consensus)) * 100


def build_financial_metrics(
    *,
    ticker: str,
    fiscal_period: str,
    eps: float | None = None,
    eps_consensus: float | None = None,
    eps_surprise_pct: float | None = None,
    revenue: float | None = None,
    revenue_consensus: float | None = None,
    revenue_surprise_pct: float | None = None,
    operating_margin_pct: float | None = None,
    operating_cash_flow: float | None = None,
    free_cash_flow: float | None = None,
    capex: float | None = None,
    guidance: str | None = None,
) -> FinancialMetrics:
    """Build normalized financial metrics passed to workflow agents."""
    if eps_surprise_pct is None:
        eps_surprise_pct = calculate_surprise_pct(eps, eps_consensus)
    if revenue_surprise_pct is None:
        revenue_surprise_pct = calculate_surprise_pct(revenue, revenue_consensus)
    if free_cash_flow is None and operating_cash_flow is not None and capex is not None:
        free_cash_flow = operating_cash_flow - abs(capex)

    return FinancialMetrics(
        ticker=ticker,
        fiscal_period=fiscal_period,
        eps=eps,
        eps_consensus=eps_consensus,
        eps_surprise_pct=eps_surprise_pct,
        revenue=revenue,
        revenue_consensus=revenue_consensus,
        revenue_surprise_pct=revenue_surprise_pct,
        operating_margin_pct=operating_margin_pct,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=free_cash_flow,
        capex=capex,
        guidance=guidance,
        source_refs=[
            SourceRef(
                source_id=f"financial_api:{ticker.upper()}:{fiscal_period}",
                source_type=SourceType.FINANCIAL_API,
                metric_name="consensus_snapshot",
                title="Financial API consensus snapshot",
            )
        ],
    )


def fetch_filing_html(url: str) -> str:
    """Fetch a SEC filing HTML. Caches under samples/cache/ to keep
    iteration cheap and deterministic (dev/prod parity, factor X)."""
    import hashlib

    import requests

    cache_dir = Path("samples/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:12]
    cache_path = cache_dir / f"{key}.html"

    if cache_path.exists():
        log.info("filing.cache_hit", url=url)
        return cache_path.read_text(encoding="utf-8")

    ua = os.getenv("SEC_USER_AGENT", "earnings-debate-agent contact@example.com")
    r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    cache_path.write_text(r.text, encoding="utf-8")
    log.info("filing.fetched", url=url, bytes=len(r.text))
    return r.text


def segment_filing(html: str) -> list[DocumentSection]:
    """Split filing into typed sections by scanning headers."""
    soup = BeautifulSoup(html, "lxml")
    # Collect text from common structural elements
    blocks = []
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "td"]):
        text = tag.get_text(" ", strip=True)
        if 80 <= len(text) <= 4000:
            blocks.append(text)

    sections: dict[str, list[str]] = {k: [] for k in SECTION_PATTERNS}
    sections["other"] = []
    for b in blocks:
        matched = False
        for name, pattern in SECTION_PATTERNS.items():
            if pattern.search(b):
                sections[name].append(b)
                matched = True
                break
        if not matched:
            sections["other"].append(b)

    result: list[DocumentSection] = []
    for name, chunks in sections.items():
        if not chunks:
            continue
        # Cap each section — context budget discipline
        joined = "\n\n".join(chunks)[:8000]
        section_id = f"filing:{name}"
        result.append(
            DocumentSection(
                section_id=section_id,
                source_ref=SourceRef(
                    source_id=section_id,
                    source_type=SourceType.FILING,
                    document_id="filing-html",
                    section_id=section_id,
                    title=f"Filing section: {name}",
                ),
                heading=name,
                text=joined,
            )
        )

    log.info("filing.segmented", sections={s.heading: len(s.text) for s in result})
    return result


def fetch_consensus(ticker: str, fiscal_period: str) -> FinancialMetrics:
    """Pull actual & consensus EPS and revenue from yfinance.

    NOTE: yfinance scrapes Yahoo Finance and the schema occasionally
    changes. This function is intentionally defensive — it fills what
    it can and leaves the rest as None for downstream agents to handle.
    """
    t = yf.Ticker(ticker)

    eps_actual = None
    eps_consensus = None
    eps_surprise_pct = None
    revenue_actual = None
    try:
        earnings_dates = t.earnings_dates
        if earnings_dates is not None and not earnings_dates.empty:
            row = earnings_dates.iloc[0]  # most recent
            eps_actual = safe_float(row.get("Reported EPS"))
            eps_consensus = safe_float(row.get("EPS Estimate"))
            eps_surprise_pct = safe_float(row.get("Surprise(%)"))
    except Exception as e:
        log.warning("yfinance.eps_fetch_failed", error=str(e))

    try:
        quarterly_financials = t.quarterly_financials
        if quarterly_financials is not None and not quarterly_financials.empty:
            if "Total Revenue" in quarterly_financials.index:
                revenue_actual = safe_float(quarterly_financials.loc["Total Revenue"].iloc[0])
    except Exception as e:
        log.warning("yfinance.revenue_fetch_failed", error=str(e))

    return build_financial_metrics(
        ticker=ticker,
        fiscal_period=fiscal_period,
        eps=eps_actual,
        eps_consensus=eps_consensus,
        eps_surprise_pct=eps_surprise_pct,
        revenue=revenue_actual,
    )
