import pytest

from src.metric_normalizer import (
    classify_metric_scope,
    derive_total_from_segments,
    normalize_metric_key,
    normalize_raw_metric,
    normalize_raw_metrics,
    resolve_canonical_metric,
)
from src.preprocessor import build_financial_metrics
from src.workflow_models import NormalizedMetric, UnmappedMetric


@pytest.mark.parametrize(
    "raw_key",
    ["Total Revenue", "TotalRevenue", "total_revenue", "total-revenue"],
)
def test_yfinance_revenue_aliases_resolve_to_same_canonical_metric(raw_key):
    assert normalize_metric_key(raw_key) == "totalrevenue"
    assert resolve_canonical_metric("yfinance", raw_key) == "revenue"


@pytest.mark.parametrize(
    "raw_key",
    [
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
)
def test_sec_revenue_tags_resolve_to_revenue(raw_key):
    assert resolve_canonical_metric("sec", raw_key) == "revenue"


def test_unknown_raw_key_can_be_kept_as_unmapped_metric():
    raw_key = "DefinitelyNotAKnownMetric"

    assert resolve_canonical_metric("sec", raw_key) is None

    unmapped = UnmappedMetric(
        raw_key=raw_key,
        value=123.0,
        unit="USD",
        period="2025Q3",
        source="sec",
        reason="no_alias_match",
    )

    assert unmapped.raw_key == raw_key
    assert unmapped.value == 123.0


def test_normalize_raw_metric_routes_segment_fact_without_collapsing_to_total():
    metric = normalize_raw_metric(
        source="sec",
        raw_key="RevenueFromContractWithCustomerExcludingAssessedTax",
        value=100.0,
        unit="USD",
        period="2025Q3",
        axis="BusinessSegmentAxis",
        member="DataCenterMember",
    )

    assert isinstance(metric, NormalizedMetric)
    assert metric.canonical_key == "revenue"
    assert metric.scope == "segment"
    assert metric.member == "DataCenterMember"


def test_normalize_raw_metrics_can_flow_into_financial_metrics_buckets():
    normalized, unmapped = normalize_raw_metrics(
        "sec",
        [
            {
                "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "value": 100.0,
                "unit": "USD",
                "period": "2025Q3",
                "axis": "BusinessSegmentAxis",
                "member": "DataCenterMember",
            },
            {
                "tag": "IssuerSpecificCloudMetric",
                "value": 5.0,
                "unit": "USD",
                "period": "2025Q3",
            },
        ],
    )

    metrics = build_financial_metrics(
        ticker="NVDA",
        fiscal_period="2025Q3",
        segment_metrics=normalized,
        unmapped_metrics=unmapped,
    )

    assert metrics.revenue is None
    assert metrics.segment_metrics[0].canonical_key == "revenue"
    assert metrics.segment_metrics[0].scope == "segment"
    assert metrics.unmapped_metrics[0].raw_key == "IssuerSpecificCloudMetric"
    assert metrics.unmapped_metrics[0].reason == "no_alias_match"


@pytest.mark.parametrize(
    ("axis", "member", "expected"),
    [
        (None, None, "consolidated"),
        ("BusinessSegmentAxis", "Cloud", "segment"),
        ("ProductOrServiceAxis", "GPU", "segment"),
        ("GeographicRegionAxis", "US", "segment"),
        ("StatementClassOfStockAxis", "Common", "dimensional"),
    ],
)
def test_classify_metric_scope(axis, member, expected):
    assert classify_metric_scope(axis, member) == expected


def _segment_metric(
    member: str,
    *,
    value: float = 10.0,
    axis: str = "BusinessSegmentAxis",
    period: str = "2025Q3",
    unit: str = "USD",
) -> NormalizedMetric:
    return NormalizedMetric(
        canonical_key="revenue",
        raw_key="RevenueFromContractWithCustomerExcludingAssessedTax",
        value=value,
        unit=unit,
        period=period,
        source="sec",
        axis=axis,
        member=member,
        scope="segment",
    )


def test_derive_total_from_segments_sums_same_axis_period_unit_without_duplicate_members():
    total = derive_total_from_segments(
        [_segment_metric("Cloud", value=100.0), _segment_metric("Gaming", value=50.0)]
    )

    assert total == 150.0


def test_derive_total_from_segments_rejects_duplicate_members_and_mixed_axis():
    assert derive_total_from_segments([_segment_metric("Cloud"), _segment_metric("Cloud")]) is None
    assert (
        derive_total_from_segments(
            [_segment_metric("Cloud"), _segment_metric("US", axis="GeographicRegionAxis")]
        )
        is None
    )
