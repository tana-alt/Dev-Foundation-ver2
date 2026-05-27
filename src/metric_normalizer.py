"""Normalize external financial metric names into canonical workflow keys."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, Literal, cast

from .workflow_models import NormalizedMetric, UnmappedMetric

CanonicalMetricKey = Literal[
    "revenue",
    "eps_basic",
    "eps_diluted",
    "operating_income",
    "operating_margin",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
]

MetricScope = Literal["consolidated", "segment", "dimensional"]


CANONICAL_METRICS: set[str] = {
    "revenue",
    "eps_basic",
    "eps_diluted",
    "operating_income",
    "operating_margin",
    "operating_cash_flow",
    "capex",
    "free_cash_flow",
}


SOURCE_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "yfinance": {
        "revenue": (
            "TotalRevenue",
            "Total Revenue",
            "OperatingRevenue",
            "Operating Revenue",
        ),
        "eps_basic": ("BasicEPS", "Basic EPS"),
        "eps_diluted": ("DilutedEPS", "Diluted EPS"),
        "operating_income": ("OperatingIncome", "Operating Income"),
        "operating_margin": ("OperatingMargin", "Operating Margin"),
        "operating_cash_flow": (
            "OperatingCashFlow",
            "Cash Flow From Continuing Operating Activities",
            "Total Cash From Operating Activities",
        ),
        "capex": (
            "CapitalExpenditure",
            "Capital Expenditure",
            "Capital Expenditures",
        ),
        "free_cash_flow": ("FreeCashFlow", "Free Cash Flow"),
    },
    "sec": {
        "revenue": (
            "Revenues",
            "SalesRevenueNet",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
        ),
        "eps_basic": ("EarningsPerShareBasic",),
        "eps_diluted": ("EarningsPerShareDiluted",),
        "operating_income": ("OperatingIncomeLoss",),
        "operating_margin": ("OperatingMargin",),
        "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
        "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
        "free_cash_flow": ("FreeCashFlow",),
    },
}

SEGMENT_AXIS_MARKERS = (
    "segment",
    "business",
    "product",
    "service",
    "geographic",
    "region",
    "market",
)


def normalize_metric_key(raw_key: object) -> str:
    """Collapse case and separators so source aliases can be matched exactly."""
    return re.sub(r"[^a-z0-9]+", "", str(raw_key).lower())


def _normalized_aliases(source: str) -> dict[str, str]:
    aliases = SOURCE_ALIASES.get(source.lower(), {})
    normalized: dict[str, str] = {}
    for canonical_key, raw_aliases in aliases.items():
        for alias in raw_aliases:
            normalized[normalize_metric_key(alias)] = canonical_key
    return normalized


def resolve_canonical_metric(source: str, raw_key: object) -> CanonicalMetricKey | None:
    """Return the canonical metric key for a source/raw key exact alias match."""
    canonical_key = _normalized_aliases(source).get(normalize_metric_key(raw_key))
    if canonical_key is None:
        return None
    return cast(CanonicalMetricKey, canonical_key)


def classify_metric_scope(axis: str | None = None, member: str | None = None) -> MetricScope:
    """Classify consolidated vs segment/dimensional facts from axis/member data."""
    if not axis and not member:
        return "consolidated"

    axis_normalized = axis.lower() if axis else ""
    if any(marker in axis_normalized for marker in SEGMENT_AXIS_MARKERS):
        return "segment"
    return "dimensional"


def normalize_raw_metric(
    *,
    source: str,
    raw_key: object,
    value: float | None = None,
    unit: str | None = None,
    period: str | None = None,
    axis: str | None = None,
    member: str | None = None,
) -> NormalizedMetric | UnmappedMetric:
    """Convert one raw source fact into a canonical or explicitly unmapped metric."""
    raw_key_text = str(raw_key)
    scope = classify_metric_scope(axis, member)
    canonical_key = resolve_canonical_metric(source, raw_key_text)

    if canonical_key is None:
        return UnmappedMetric(
            raw_key=raw_key_text,
            value=value,
            unit=unit,
            period=period,
            source=source,
            axis=axis,
            member=member,
            scope=scope,
            reason="no_alias_match",
        )
    return NormalizedMetric(
        canonical_key=canonical_key,
        raw_key=raw_key_text,
        value=value,
        unit=unit,
        period=period,
        source=source,
        axis=axis,
        member=member,
        scope=scope,
    )


def normalize_raw_metrics(
    source: str,
    raw_metrics: Iterable[Mapping[str, Any]],
) -> tuple[list[NormalizedMetric], list[UnmappedMetric]]:
    """Route raw source facts into normalized and unmapped metric buckets."""
    normalized: list[NormalizedMetric] = []
    unmapped: list[UnmappedMetric] = []

    for raw_metric in raw_metrics:
        routed = normalize_raw_metric(
            source=source,
            raw_key=raw_metric.get("raw_key") or raw_metric.get("tag") or raw_metric.get("key"),
            value=raw_metric.get("value"),
            unit=raw_metric.get("unit"),
            period=raw_metric.get("period"),
            axis=raw_metric.get("axis"),
            member=raw_metric.get("member"),
        )
        if isinstance(routed, NormalizedMetric):
            normalized.append(routed)
        else:
            unmapped.append(routed)

    return normalized, unmapped


def derive_total_from_segments(metrics: Iterable[NormalizedMetric]) -> float | None:
    """Strictly sum comparable segment facts without mutating consolidated metrics."""
    facts = list(metrics)
    if not facts:
        return None

    first = facts[0]
    if first.scope != "segment" or not first.axis or not first.member:
        return None

    members: set[str] = set()
    total = 0.0
    for fact in facts:
        if (
            fact.scope != "segment"
            or fact.canonical_key != first.canonical_key
            or fact.unit != first.unit
            or fact.period != first.period
            or fact.axis != first.axis
            or not fact.member
            or fact.value is None
        ):
            return None
        if fact.member in members:
            return None
        members.add(fact.member)
        total += fact.value

    return total
