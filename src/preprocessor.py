"""Preprocessor: fetches filing + market consensus, then segments the
filing into typed sections.

This module is THE answer to context engineering: the LLM never sees
the raw 80-page filing. By the time anything reaches an agent, it has
been (a) chunked semantically and (b) annotated with structured numbers.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
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
    MetricStoreEntry,
    MetricStorePeriodRole,
    NormalizedMetric,
    PresentationMetricHint,
    SelectionMethod,
    SourceProvider,
    SourceRef,
    SourceType,
    TemporalPeriodRole,
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
YFINANCE_DATE_WINDOW_DAYS = 7


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
        fiscal_period=document_file.fiscal_period,
        period_role=document_file.period_role or "target_period_document",
        published_date=document_file.published_date,
    )
    try:
        return DocumentSection(
            section_id=section_id,
            source_ref=source_ref,
            heading=heading,
            text=text,
            start_page=page,
            end_page=page,
            fiscal_period=document_file.fiscal_period,
            published_date=document_file.published_date,
            period_role=document_file.period_role or "target_period_document",
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


def _date_from_external(value: Any) -> date | None:
    """Normalize pandas/datetime/string dates from external provider indexes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        try:
            return value.date()
        except TypeError:
            pass
    try:
        import pandas as pd

        parsed = pd.Timestamp(value)
        if parsed is pd.NaT:
            return None
        return parsed.date()
    except Exception:
        return None


def _coerce_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return _date_from_external(value)


def _prior_sequential_period(fiscal_period: str) -> str:
    year = int(fiscal_period[:4])
    quarter = int(fiscal_period[-1])
    if quarter == 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


def _validate_prior_fiscal_period(fiscal_period: str, prior_fiscal_period: str | None) -> str:
    expected = _prior_sequential_period(fiscal_period)
    if prior_fiscal_period is not None and prior_fiscal_period != expected:
        raise ValueError("prior_fiscal_period must be the immediately preceding fiscal quarter")
    return expected


def _earnings_dates_frame(ticker_obj: Any) -> Any:
    if hasattr(ticker_obj, "get_earnings_dates"):
        try:
            return ticker_obj.get_earnings_dates(limit=16)
        except TypeError:
            return ticker_obj.get_earnings_dates()
    return getattr(ticker_obj, "earnings_dates", None)


def _select_earnings_row(frame: Any, target_date: date | None) -> tuple[Any | None, date | None]:
    if frame is None or getattr(frame, "empty", True) or target_date is None:
        return None, None
    for index, row in frame.iterrows():
        row_date = _date_from_external(index)
        if row_date == target_date:
            return row, row_date
    return None, None


def _select_prior_earnings_row(
    frame: Any,
    target_date: date | None,
) -> tuple[Any | None, date | None]:
    if frame is None or getattr(frame, "empty", True) or target_date is None:
        return None, None
    candidates: list[tuple[date, Any]] = []
    for index, row in frame.iterrows():
        row_date = _date_from_external(index)
        if row_date is not None and row_date < target_date:
            candidates.append((row_date, row))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][0]


def _metric_value_at_column(frame: Any, canonical_key: str, column: Any) -> float | None:
    if frame is None or getattr(frame, "empty", True) or column is None:
        return None
    for raw_key in frame.index:
        if resolve_canonical_metric("yfinance", raw_key) == canonical_key:
            row = frame.loc[raw_key]
            if hasattr(row, "__getitem__"):
                return safe_float(row[column])
            return safe_float(row)
    return None


def _select_table_column(
    frame: Any,
    target_period_end_date: date | None,
) -> tuple[Any | None, date | None, SelectionMethod | None]:
    if frame is None or getattr(frame, "empty", True) or target_period_end_date is None:
        return None, None, None
    dated_columns: list[tuple[date, Any]] = []
    for column in frame.columns:
        column_date = _date_from_external(column)
        if column_date is None:
            continue
        if column_date == target_period_end_date:
            return column, column_date, "period_end_exact"
        dated_columns.append((column_date, column))
    if not dated_columns:
        return None, None, None
    closest_date, closest_column = min(
        dated_columns,
        key=lambda item: abs((item[0] - target_period_end_date).days),
    )
    if abs((closest_date - target_period_end_date).days) <= YFINANCE_DATE_WINDOW_DAYS:
        return closest_column, closest_date, "provider_column_date_window"
    return None, None, None


def _select_prior_table_column(
    frame: Any,
    target_column_date: date | None,
) -> tuple[Any | None, date | None, SelectionMethod | None]:
    if frame is None or getattr(frame, "empty", True) or target_column_date is None:
        return None, None, None
    candidates: list[tuple[date, Any]] = []
    for column in frame.columns:
        column_date = _date_from_external(column)
        if column_date is not None and column_date < target_column_date:
            candidates.append((column_date, column))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda item: item[0], reverse=True)
    prior_date, prior_column = candidates[0]
    return prior_column, prior_date, "period_end_exact"


def _metric_store_source_name(source_provider: str | None) -> str:
    if source_provider == "yfinance":
        return "Yahoo Finance via yfinance"
    if source_provider == "sec":
        return "SEC filing-derived metrics"
    if source_provider == "manual":
        return "Manual financial metrics input"
    return "Financial metrics input"


def _metric_unit(metric_name: str, currency: str) -> str:
    if metric_name.startswith("eps"):
        return f"{currency}/share"
    if metric_name.endswith("_pct"):
        return "%"
    return currency


def _metric_source_ref(
    *,
    ticker: str,
    fiscal_period: str,
    metric_name: str,
    period_role: TemporalPeriodRole,
    source_name: str,
    source_type: SourceType = SourceType.FINANCIAL_API,
    as_of_date: date | None = None,
    data_cutoff_date: date | None = None,
) -> SourceRef:
    return SourceRef(
        source_id=f"{source_type.value}:{ticker.upper()}:{fiscal_period}:{metric_name}",
        source_type=source_type,
        metric_name=metric_name,
        title=source_name,
        fiscal_period=fiscal_period,
        period_role=period_role,
        as_of_date=as_of_date,
        data_cutoff_date=data_cutoff_date,
    )


def _metric_store_entry(
    *,
    ticker: str,
    fiscal_period: str,
    metric_name: str,
    value: float | None,
    unit: str,
    source_name: str,
    period_role: MetricStorePeriodRole,
    source_type: SourceType = SourceType.FINANCIAL_API,
    as_of_date: date | None = None,
    data_cutoff_date: date | None = None,
) -> MetricStoreEntry | None:
    if value is None:
        return None
    return MetricStoreEntry(
        metric_name=metric_name,
        value=value,
        unit=unit,
        source_type=source_type,
        source_name=source_name,
        fiscal_period=fiscal_period,
        period_role=period_role,
        source_ref=_metric_source_ref(
            ticker=ticker,
            fiscal_period=fiscal_period,
            metric_name=metric_name,
            period_role=period_role,
            source_name=source_name,
            source_type=source_type,
            as_of_date=as_of_date,
            data_cutoff_date=data_cutoff_date,
        ),
    )


def _build_metric_store(
    *,
    ticker: str,
    fiscal_period: str,
    currency: str,
    source_provider: SourceProvider | None,
    earnings_date: date | None,
    data_cutoff_date: date | None,
    eps: float | None,
    eps_consensus: float | None,
    revenue: float | None,
    revenue_consensus: float | None,
    operating_margin_pct: float | None,
    operating_cash_flow: float | None,
    free_cash_flow: float | None,
    capex: float | None,
) -> list[MetricStoreEntry]:
    source_name = _metric_store_source_name(source_provider)
    as_of_date = earnings_date or data_cutoff_date
    specs: list[tuple[str, float | None, MetricStorePeriodRole, SourceType]] = [
        ("eps", eps, "reported_period_actuals", SourceType.FINANCIAL_API),
        (
            "eps_consensus",
            eps_consensus,
            "consensus_for_reported_period",
            SourceType.FINANCIAL_API,
        ),
        ("revenue", revenue, "reported_period_actuals", SourceType.FINANCIAL_API),
        (
            "revenue_consensus",
            revenue_consensus,
            "consensus_for_reported_period",
            SourceType.FINANCIAL_API,
        ),
        (
            "operating_margin_pct",
            operating_margin_pct,
            "reported_period_actuals",
            SourceType.FINANCIAL_API,
        ),
        (
            "operating_cash_flow",
            operating_cash_flow,
            "reported_period_actuals",
            SourceType.FINANCIAL_API,
        ),
        ("free_cash_flow", free_cash_flow, "reported_period_actuals", SourceType.FINANCIAL_API),
        ("capex", capex, "reported_period_actuals", SourceType.FINANCIAL_API),
    ]
    entries: list[MetricStoreEntry] = []
    for metric_name, value, period_role, source_type in specs:
        entry = _metric_store_entry(
            ticker=ticker,
            fiscal_period=fiscal_period,
            metric_name=metric_name,
            value=value,
            unit=_metric_unit(metric_name, currency),
            source_name=source_name,
            period_role=period_role,
            source_type=source_type,
            as_of_date=as_of_date,
            data_cutoff_date=data_cutoff_date,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def _build_prior_sequential_metric_store(
    *,
    ticker: str,
    fiscal_period: str,
    currency: str,
    source_provider: SourceProvider | None,
    source_row_date: date | None,
    data_cutoff_date: date | None,
    metrics: dict[str, Any],
) -> list[MetricStoreEntry]:
    source_name = _metric_store_source_name(source_provider)
    as_of_date = source_row_date or data_cutoff_date
    specs = [
        ("eps", safe_float(metrics.get("eps"))),
        ("revenue", safe_float(metrics.get("revenue"))),
        ("operating_cash_flow", safe_float(metrics.get("operating_cash_flow"))),
        ("free_cash_flow", safe_float(metrics.get("free_cash_flow"))),
        ("capex", safe_float(metrics.get("capex"))),
    ]
    entries: list[MetricStoreEntry] = []
    for metric_name, value in specs:
        entry = _metric_store_entry(
            ticker=ticker,
            fiscal_period=fiscal_period,
            metric_name=metric_name,
            value=value,
            unit=_metric_unit(metric_name, currency),
            source_name=source_name,
            period_role="prior_sequential_period_actuals",
            source_type=SourceType.FINANCIAL_API,
            as_of_date=as_of_date,
            data_cutoff_date=data_cutoff_date,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def _dedupe_source_refs(source_refs: list[SourceRef]) -> list[SourceRef]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    result: list[SourceRef] = []
    for source_ref in source_refs:
        key = (
            source_ref.source_id,
            source_ref.source_type.value,
            source_ref.metric_name,
            source_ref.period_role,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(source_ref)
    return result


def build_financial_metrics(
    *,
    ticker: str,
    fiscal_period: str,
    currency: str = "USD",
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
    period_end_date: date | None = None,
    period_role: TemporalPeriodRole = "reported_period_actuals",
    earnings_date: date | None = None,
    source_provider: SourceProvider | None = None,
    source_row_date: date | None = None,
    source_table_column_date: date | None = None,
    data_cutoff_date: date | None = None,
    selection_method: SelectionMethod | None = None,
    temporal_snapshots: dict[str, dict] | None = None,
    warnings: list[str] | None = None,
    metric_store: list[MetricStoreEntry] | None = None,
    metric_store_extras: list[MetricStoreEntry] | None = None,
    presentation_metric_hints: list[PresentationMetricHint] | None = None,
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
    metric_store_entries = metric_store or _build_metric_store(
        ticker=ticker,
        fiscal_period=fiscal_period,
        currency=currency.upper().strip(),
        source_provider=source_provider,
        earnings_date=earnings_date,
        data_cutoff_date=data_cutoff_date,
        eps=eps,
        eps_consensus=eps_consensus,
        revenue=revenue,
        revenue_consensus=revenue_consensus,
        operating_margin_pct=operating_margin_pct,
        operating_cash_flow=operating_cash_flow,
        free_cash_flow=free_cash_flow,
        capex=capex,
    )
    if metric_store_extras:
        metric_store_entries = [*metric_store_entries, *metric_store_extras]
    source_refs = _dedupe_source_refs([entry.source_ref for entry in metric_store_entries])
    if not source_refs:
        source_refs = [
            SourceRef(
                source_id=f"financial_api:{ticker.upper()}:{fiscal_period}",
                source_type=SourceType.FINANCIAL_API,
                metric_name="consensus_snapshot",
                title="Financial API consensus snapshot",
                fiscal_period=fiscal_period,
                period_role="reported_period_actuals",
                as_of_date=earnings_date or data_cutoff_date,
                data_cutoff_date=data_cutoff_date,
            )
        ]

    return FinancialMetrics(
        ticker=ticker,
        fiscal_period=fiscal_period,
        period_end_date=period_end_date,
        currency=currency,
        period_role=period_role,
        earnings_date=earnings_date,
        source_provider=source_provider,
        source_row_date=source_row_date,
        source_table_column_date=source_table_column_date,
        data_cutoff_date=data_cutoff_date,
        selection_method=selection_method,
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
        metric_store=metric_store_entries,
        presentation_metric_hints=presentation_metric_hints or [],
        segment_metrics=segment_metrics or [],
        unmapped_metrics=unmapped_metrics or [],
        temporal_snapshots=temporal_snapshots or {},
        warnings=warnings or [],
        source_refs=source_refs,
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


def fetch_consensus(
    ticker: str,
    fiscal_period: str,
    *,
    target_earnings_date: date | str | None = None,
    target_period_end_date: date | str | None = None,
    prior_fiscal_period: str | None = None,
    financial_data_as_of: date | str | None = None,
) -> FinancialMetrics:
    """Pull actual & consensus EPS and revenue from yfinance.

    NOTE: yfinance scrapes Yahoo Finance and the schema occasionally
    changes. This function is intentionally defensive — it fills what
    it can and leaves the rest as None for downstream agents to handle.
    """
    prior_fiscal_period = _validate_prior_fiscal_period(fiscal_period, prior_fiscal_period)
    target_earnings_date = _coerce_date(target_earnings_date)
    target_period_end_date = _coerce_date(target_period_end_date)
    financial_data_as_of = _coerce_date(financial_data_as_of)
    t = yf.Ticker(ticker)

    eps_actual = None
    eps_consensus = None
    eps_surprise_pct = None
    source_row_date = None
    prior_row_date = None
    revenue_actual = None
    operating_cash_flow = None
    capex = None
    free_cash_flow = None
    source_table_column_date = None
    selection_method = None
    warnings: list[str] = []
    prior_snapshot: dict[str, Any] | None = None
    if (
        financial_data_as_of is not None
        and target_earnings_date is not None
        and financial_data_as_of < target_earnings_date
    ):
        warning = "financial_data_as_of is before target_earnings_date; yfinance actuals were not selected"
        return build_financial_metrics(
            ticker=ticker,
            fiscal_period=fiscal_period,
            period_end_date=target_period_end_date,
            earnings_date=target_earnings_date,
            source_provider="yfinance",
            data_cutoff_date=financial_data_as_of,
            temporal_snapshots={
                "reported_period_actuals": {
                    "bucket": "reported_period_actuals",
                    "ticker": ticker.upper(),
                    "fiscal_period": fiscal_period,
                    "period_end_date": target_period_end_date.isoformat()
                    if target_period_end_date
                    else None,
                    "earnings_date": target_earnings_date.isoformat(),
                    "source_provider": "yfinance",
                    "metrics": {},
                    "warnings": [warning],
                },
                "pre_earnings_consensus": {
                    "bucket": "pre_earnings_consensus",
                    "ticker": ticker.upper(),
                    "fiscal_period": fiscal_period,
                    "as_of_date": financial_data_as_of.isoformat(),
                    "source_provider": "yfinance",
                    "metrics": {},
                    "warnings": [warning],
                },
            },
            warnings=[warning],
        )
    try:
        earnings_dates = _earnings_dates_frame(t)
        row, source_row_date = _select_earnings_row(earnings_dates, target_earnings_date)
        if row is not None:
            eps_actual = safe_float(row.get("Reported EPS"))
            eps_consensus = safe_float(row.get("EPS Estimate"))
            eps_surprise_pct = safe_float(row.get("Surprise(%)"))
            prior_row, prior_row_date = _select_prior_earnings_row(
                earnings_dates,
                source_row_date,
            )
            if prior_row is not None:
                prior_snapshot = {
                    "bucket": "prior_sequential_period_actuals",
                    "ticker": ticker.upper(),
                    "fiscal_period": prior_fiscal_period,
                    "source_provider": "yfinance",
                    "source_row_date": prior_row_date.isoformat() if prior_row_date else None,
                    "metrics": {
                        "eps": safe_float(prior_row.get("Reported EPS")),
                        "eps_consensus": safe_float(prior_row.get("EPS Estimate")),
                        "eps_surprise_pct": safe_float(prior_row.get("Surprise(%)")),
                    },
                }
        elif target_earnings_date is None:
            warnings.append("yfinance target_earnings_date was not provided; EPS row not selected")
        else:
            warnings.append(
                f"yfinance has no earnings row for target_earnings_date={target_earnings_date.isoformat()}"
            )
    except Exception as e:
        log.warning("yfinance.eps_fetch_failed", error=str(e))
        warnings.append(f"yfinance EPS fetch failed: {e}")

    try:
        quarterly_financials = t.quarterly_financials
        target_column, source_table_column_date, financial_selection = _select_table_column(
            quarterly_financials,
            target_period_end_date,
        )
        if target_column is not None:
            revenue_actual = _metric_value_at_column(quarterly_financials, "revenue", target_column)
            selection_method = financial_selection
            if prior_snapshot is None:
                prior_snapshot = {
                    "bucket": "prior_sequential_period_actuals",
                    "ticker": ticker.upper(),
                    "fiscal_period": prior_fiscal_period,
                    "source_provider": "yfinance",
                    "metrics": {},
                }
            prior_column, prior_column_date, _ = _select_prior_table_column(
                quarterly_financials,
                source_table_column_date,
            )
            prior_snapshot["source_table_column_date"] = (
                prior_column_date.isoformat() if prior_column_date else None
            )
            prior_snapshot["metrics"]["revenue"] = _metric_value_at_column(
                quarterly_financials,
                "revenue",
                prior_column,
            )
        elif target_period_end_date is None:
            warnings.append(
                "target_period_end_date was not provided; yfinance P&L column not selected"
            )
        else:
            warnings.append(
                f"yfinance has no P&L column matching target_period_end_date={target_period_end_date.isoformat()}"
            )
    except Exception as e:
        log.warning("yfinance.revenue_fetch_failed", error=str(e))
        warnings.append(f"yfinance revenue fetch failed: {e}")

    try:
        quarterly_cashflow = t.quarterly_cashflow
        target_column, cashflow_column_date, cashflow_selection = _select_table_column(
            quarterly_cashflow,
            target_period_end_date,
        )
        if target_column is not None:
            operating_cash_flow = _metric_value_at_column(
                quarterly_cashflow,
                "operating_cash_flow",
                target_column,
            )
            capex = _metric_value_at_column(quarterly_cashflow, "capex", target_column)
            free_cash_flow = _metric_value_at_column(
                quarterly_cashflow,
                "free_cash_flow",
                target_column,
            )
            source_table_column_date = source_table_column_date or cashflow_column_date
            selection_method = selection_method or cashflow_selection
            if prior_snapshot is None:
                prior_snapshot = {
                    "bucket": "prior_sequential_period_actuals",
                    "ticker": ticker.upper(),
                    "fiscal_period": prior_fiscal_period,
                    "source_provider": "yfinance",
                    "metrics": {},
                }
            prior_column, prior_column_date, _ = _select_prior_table_column(
                quarterly_cashflow,
                cashflow_column_date,
            )
            prior_snapshot["source_table_column_date"] = prior_snapshot.get(
                "source_table_column_date"
            ) or (prior_column_date.isoformat() if prior_column_date else None)
            prior_snapshot["metrics"]["operating_cash_flow"] = _metric_value_at_column(
                quarterly_cashflow,
                "operating_cash_flow",
                prior_column,
            )
            prior_snapshot["metrics"]["capex"] = _metric_value_at_column(
                quarterly_cashflow,
                "capex",
                prior_column,
            )
            prior_snapshot["metrics"]["free_cash_flow"] = _metric_value_at_column(
                quarterly_cashflow,
                "free_cash_flow",
                prior_column,
            )
        elif target_period_end_date is not None:
            warnings.append(
                f"yfinance has no cash-flow column matching target_period_end_date={target_period_end_date.isoformat()}"
            )
    except Exception as e:
        log.warning("yfinance.cashflow_fetch_failed", error=str(e))
        warnings.append(f"yfinance cash-flow fetch failed: {e}")

    temporal_snapshots: dict[str, dict] = {
        "reported_period_actuals": {
            "bucket": "reported_period_actuals",
            "ticker": ticker.upper(),
            "fiscal_period": fiscal_period,
            "period_end_date": target_period_end_date.isoformat()
            if target_period_end_date
            else None,
            "earnings_date": target_earnings_date.isoformat() if target_earnings_date else None,
            "source_provider": "yfinance",
            "source_row_date": source_row_date.isoformat() if source_row_date else None,
            "source_table_column_date": source_table_column_date.isoformat()
            if source_table_column_date
            else None,
            "selection_method": selection_method,
            "metrics": {
                "eps": eps_actual,
                "revenue": revenue_actual,
                "operating_cash_flow": operating_cash_flow,
                "free_cash_flow": free_cash_flow,
                "capex": capex,
            },
            "warnings": warnings,
        },
        "pre_earnings_consensus": {
            "bucket": "pre_earnings_consensus",
            "ticker": ticker.upper(),
            "fiscal_period": fiscal_period,
            "as_of_date": target_earnings_date.isoformat() if target_earnings_date else None,
            "source_provider": "yfinance",
            "source_row_date": source_row_date.isoformat() if source_row_date else None,
            "metrics": {
                "eps_consensus": eps_consensus,
                "eps_surprise_pct": eps_surprise_pct,
            },
            "warnings": warnings,
        },
    }
    if prior_snapshot is not None:
        temporal_snapshots["prior_sequential_period_actuals"] = prior_snapshot

    prior_metric_store_entries = (
        _build_prior_sequential_metric_store(
            ticker=ticker,
            fiscal_period=prior_fiscal_period,
            currency="USD",
            source_provider="yfinance",
            source_row_date=prior_row_date,
            data_cutoff_date=financial_data_as_of,
            metrics=prior_snapshot.get("metrics", {}),
        )
        if prior_snapshot is not None
        else []
    )

    return build_financial_metrics(
        ticker=ticker,
        fiscal_period=fiscal_period,
        period_end_date=target_period_end_date,
        earnings_date=target_earnings_date,
        source_provider="yfinance",
        source_row_date=source_row_date,
        source_table_column_date=source_table_column_date,
        data_cutoff_date=financial_data_as_of,
        selection_method=selection_method,
        eps=eps_actual,
        eps_consensus=eps_consensus,
        eps_surprise_pct=eps_surprise_pct,
        revenue=revenue_actual,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        free_cash_flow=free_cash_flow,
        temporal_snapshots=temporal_snapshots,
        warnings=warnings,
        metric_store_extras=prior_metric_store_entries,
    )
