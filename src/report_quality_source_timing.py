"""Source timing classification for earnings-review evidence.

The main report should prefer same-period primary sources. External sources are
classified separately and are not used in the main verdict unless accepted.
"""

from __future__ import annotations

from datetime import date

from .report_quality_contracts import SourceTiming

PRIMARY_SOURCE_TYPES = {
    "filing",
    "press_release",
    "earnings_call",
    "earnings_presentation",
    "financial_api",
    "derived_metric",
    "manual_upload",
}


def _source_type_value(ref) -> str:
    value = getattr(ref, "source_type", "")
    return str(getattr(value, "value", value))


def classify_source_timing(
    ref, *, event_date: date | None = None, published_date: date | None = None
) -> SourceTiming:
    source_type = _source_type_value(ref)
    if source_type in PRIMARY_SOURCE_TYPES:
        return SourceTiming.SAME_PERIOD_PRIMARY
    if event_date is None or published_date is None:
        return SourceTiming.UNKNOWN
    delta_days = (published_date - event_date).days
    if -7 <= delta_days <= 7:
        return SourceTiming.CONTEMPORARY_EXTERNAL
    if delta_days > 7:
        return SourceTiming.POST_EVENT_EXTERNAL
    return SourceTiming.STALE_EXTERNAL


def source_timing_label(ref) -> str:
    return classify_source_timing(ref).value
