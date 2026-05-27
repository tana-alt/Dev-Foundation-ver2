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
from pydantic import ValidationError

from .metric_normalizer import resolve_canonical_metric
from .workflow_models import (
    DocumentFile,
    DocumentSection,
    FinancialMetrics,
    NormalizedMetric,
    SourceRef,
    SourceType,
    UnmappedMetric,
)

log = structlog.get_logger()


SECTION_PATTERNS = {
    "revenue": re.compile(r"(net\s+revenue|total\s+revenue|net\s+sales)", re.I),
    "eps": re.compile(r"(earnings\s+per\s+share|diluted\s+eps)", re.I),
    "guidance": re.compile(r"(outlook|guidance)", re.I),
    "segments": re.compile(r"(segment|geographic|product\s+category)", re.I),
    "risk": re.compile(r"(risk\s+factor|forward[- ]looking\s+statement)", re.I),
}

SUPPORTED_DOCUMENT_FILE_SUFFIXES = {".pdf", ".txt", ".text", ".md"}
MAX_DOCUMENT_SECTION_CHARS = 8000


class DocumentFileValidationError(ValueError):
    """Raised when a local document file cannot be converted into sections."""


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value.strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "section"


def _normalize_document_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str, *, max_chars: int = MAX_DOCUMENT_SECTION_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_chars:
            chunks.append(paragraph[:max_chars].strip())
            paragraph = paragraph[max_chars:].strip()
        current = paragraph
    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def document_files_to_sections(document_files: list[DocumentFile]) -> list[DocumentSection]:
    """Expand local PDF/text documents into validated workflow sections."""
    sections: list[DocumentSection] = []
    for document_file in document_files:
        path = Path(document_file.path).expanduser()
        if not path.exists():
            raise DocumentFileValidationError(f"document file does not exist: {document_file.path}")
        if not path.is_file():
            raise DocumentFileValidationError(f"document path is not a file: {document_file.path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_DOCUMENT_FILE_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_DOCUMENT_FILE_SUFFIXES))
            raise DocumentFileValidationError(
                f"unsupported document file extension for {document_file.path}; supported: {supported}"
            )

        if suffix == ".pdf":
            sections.extend(_pdf_file_to_sections(path, document_file))
        else:
            sections.extend(_text_file_to_sections(path, document_file))

    if document_files and not sections:
        raise DocumentFileValidationError("document_files produced no document_sections")
    return sections


def _text_file_to_sections(path: Path, document_file: DocumentFile) -> list[DocumentSection]:
    try:
        text = _normalize_document_text(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise DocumentFileValidationError(
            f"text document must be UTF-8 encoded: {document_file.path}"
        ) from exc
    if not text:
        raise DocumentFileValidationError(f"text document is empty: {document_file.path}")

    sections = []
    for index, chunk in enumerate(_chunk_text(text), start=1):
        section_id = _slug(f"{document_file.document_id}:section-{index}")
        sections.append(
            _build_document_section(
                document_file=document_file,
                section_id=section_id,
                heading=f"{document_file.title} section {index}",
                text=chunk,
            )
        )
    return sections


def _pdf_file_to_sections(path: Path, document_file: DocumentFile) -> list[DocumentSection]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentFileValidationError(
            "PDF document ingestion requires the 'pypdf' package to be installed"
        ) from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise DocumentFileValidationError(
            f"failed to read PDF document: {document_file.path}"
        ) from exc

    sections = []
    for page_index, page in enumerate(reader.pages, start=1):
        page_text = _normalize_document_text(page.extract_text() or "")
        if not page_text:
            continue
        for chunk_index, chunk in enumerate(_chunk_text(page_text), start=1):
            section_id = _slug(f"{document_file.document_id}:p{page_index}:section-{chunk_index}")
            sections.append(
                _build_document_section(
                    document_file=document_file,
                    section_id=section_id,
                    heading=f"{document_file.title} page {page_index}",
                    text=chunk,
                    page=page_index,
                )
            )

    if not sections:
        raise DocumentFileValidationError(
            f"PDF document yielded no extractable text: {document_file.path}"
        )
    return sections


def _build_document_section(
    *,
    document_file: DocumentFile,
    section_id: str,
    heading: str,
    text: str,
    page: int | None = None,
) -> DocumentSection:
    source_ref = SourceRef(
        source_id=section_id,
        source_type=document_file.source_type,
        document_id=document_file.document_id,
        section_id=section_id,
        page=page,
        title=document_file.title,
    )
    try:
        return DocumentSection(
            section_id=section_id,
            source_ref=source_ref,
            heading=heading,
            text=text,
            start_page=page,
            end_page=page,
        )
    except ValidationError as exc:
        raise DocumentFileValidationError(
            f"document section validation failed for {document_file.path}: {exc}"
        ) from exc


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


def _first_metric_value(frame: Any, canonical_key: str) -> float | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    for raw_key in frame.index:
        if resolve_canonical_metric("yfinance", raw_key) == canonical_key:
            row = frame.loc[raw_key]
            if hasattr(row, "iloc"):
                return safe_float(row.iloc[0])
            return safe_float(row)
    return None


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
    segment_metrics: list[NormalizedMetric] | None = None,
    unmapped_metrics: list[UnmappedMetric] | None = None,
) -> FinancialMetrics:
    """Build normalized financial metrics passed to workflow agents."""
    if eps_surprise_pct is None:
        eps_surprise_pct = calculate_surprise_pct(eps, eps_consensus)
    if revenue_surprise_pct is None:
        revenue_surprise_pct = calculate_surprise_pct(revenue, revenue_consensus)
    if operating_cash_flow is not None and capex is not None:
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
        segment_metrics=segment_metrics or [],
        unmapped_metrics=unmapped_metrics or [],
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


def segment_filing(html: str, url: str | None = None) -> list[DocumentSection]:
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
                source_ref=SourceRef.model_validate(
                    {
                        "source_id": section_id,
                        "source_type": SourceType.FILING,
                        "url": url,
                        "document_id": "filing-html",
                        "section_id": section_id,
                        "title": f"Filing section: {name}",
                    }
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
    operating_cash_flow = None
    capex = None
    free_cash_flow = None
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
            revenue_actual = _first_metric_value(quarterly_financials, "revenue")
    except Exception as e:
        log.warning("yfinance.revenue_fetch_failed", error=str(e))

    try:
        quarterly_cashflow = t.quarterly_cashflow
        if quarterly_cashflow is not None and not quarterly_cashflow.empty:
            operating_cash_flow = _first_metric_value(quarterly_cashflow, "operating_cash_flow")
            capex = _first_metric_value(quarterly_cashflow, "capex")
            free_cash_flow = _first_metric_value(quarterly_cashflow, "free_cash_flow")
    except Exception as e:
        log.warning("yfinance.cashflow_fetch_failed", error=str(e))

    return build_financial_metrics(
        ticker=ticker,
        fiscal_period=fiscal_period,
        eps=eps_actual,
        eps_consensus=eps_consensus,
        eps_surprise_pct=eps_surprise_pct,
        revenue=revenue_actual,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        free_cash_flow=free_cash_flow,
    )
