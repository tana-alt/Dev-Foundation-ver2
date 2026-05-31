"""Evidence Matrix renderer.

This renders existing EvidenceItem fields instead of changing workflow_models.py.
"""

from __future__ import annotations

from typing import Iterable

try:
    from .report_quality_source_timing import source_timing_label
except Exception:  # pragma: no cover

    def source_timing_label(ref) -> str:  # type: ignore
        return "unknown"


def escape_md_table(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("|", "\\|").strip()
    return text or "—"


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def format_evidence_value(item) -> str:
    value = getattr(item, "value", None)
    unit = getattr(item, "unit", None)
    metric_name = getattr(item, "metric_name", None)
    if value is not None:
        if isinstance(value, float) and abs(value) >= 1_000_000:
            value_text = f"{value:,.0f}"
        elif isinstance(value, float):
            value_text = f"{value:g}"
        else:
            value_text = str(value)
        parts = [value_text]
        if unit:
            parts.append(str(unit))
        if metric_name:
            parts.append(f"({metric_name})")
        return " ".join(parts)
    detail = getattr(item, "detail", "") or ""
    if detail:
        return detail[:500]
    return getattr(item, "summary", "") or "—"


def source_label(ref) -> str:
    if ref is None:
        return "—"
    locator = (
        getattr(ref, "metric_name", None)
        or getattr(ref, "section_id", None)
        or getattr(ref, "document_id", None)
        or "source"
    )
    return f"`{getattr(ref, 'source_id', 'source')}` / {locator}"


def evidence_matrix_lines(items: Iterable, *, max_items: int = 16) -> list[str]:
    material = list(items)[:max_items]
    if not material:
        return ["No evidence items were selected by the judge."]
    lines = [
        "| # | Direction | Claim | Evidence value / quote | Interpretation | Source | Timing | Confidence |",
        "|---:|---|---|---|---|---|---|---:|",
    ]
    for index, item in enumerate(material, start=1):
        ref = getattr(item, "source_ref", None)
        detail = getattr(item, "detail", "") or ""
        summary = getattr(item, "summary", "") or ""
        interpretation = detail[:240] if detail else summary
        confidence = float(getattr(item, "confidence", 0.0) or 0.0)
        lines.append(
            "| {index} | {direction} | {claim} | {value} | {interpretation} | {source} | {timing} | {confidence:.2f} |".format(
                index=index,
                direction=escape_md_table(_enum_value(getattr(item, "polarity", ""))),
                claim=escape_md_table(summary),
                value=escape_md_table(format_evidence_value(item)),
                interpretation=escape_md_table(interpretation),
                source=escape_md_table(source_label(ref)),
                timing=escape_md_table(source_timing_label(ref) if ref is not None else "unknown"),
                confidence=confidence,
            )
        )
    return lines
