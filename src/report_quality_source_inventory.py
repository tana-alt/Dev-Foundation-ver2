"""Claim-source inventory renderer."""

from __future__ import annotations

from typing import TypedDict

try:
    from .report_quality_source_timing import source_timing_label
except Exception:  # pragma: no cover

    def source_timing_label(ref) -> str:  # type: ignore
        return "unknown"


class SourceInventoryRow(TypedDict):
    source_id: object
    type: object
    locator: object
    title: object
    url: str
    timing: object
    period_role: object
    used_for: set[str]


def escape_md_table(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", " ").replace("|", "\\|").strip() or "—"


def _collect_findings(brief) -> list:
    return [
        getattr(brief, "earnings_quality_finding", None),
        getattr(brief, "cash_flow_risk_finding", None),
        getattr(brief, "management_intent_finding", None),
        getattr(brief, "guidance_finding", None),
    ]


def _source_type_value(ref) -> str:
    return str(
        getattr(
            getattr(ref, "source_type", None),
            "value",
            getattr(ref, "source_type", ""),
        )
    )


def _locator(ref) -> object:
    return (
        getattr(ref, "metric_name", None)
        or getattr(ref, "section_id", None)
        or getattr(ref, "document_id", None)
        or "source"
    )


def _url_or_locator(entry: SourceInventoryRow) -> object:
    if entry["url"]:
        return entry["url"]
    source_type = str(entry["type"])
    if source_type == "filing":
        return "no URL"
    if source_type in {"financial_api", "derived_metric"}:
        return entry["title"] or entry["source_id"]
    if source_type in {
        "earnings_presentation",
        "earnings_call",
        "press_release",
        "manual_upload",
    }:
        return entry["locator"]
    return "—"


def source_inventory_lines(brief, decision=None) -> list[str]:
    rows: dict[tuple[object, ...], SourceInventoryRow] = {}
    for finding in _collect_findings(brief):
        if finding is None:
            continue
        agent = getattr(finding, "agent_name", "UnknownAgent")
        for item in [
            *(getattr(finding, "key_evidence", []) or []),
            *(getattr(finding, "counter_evidence", []) or []),
        ]:
            ref = getattr(item, "source_ref", None)
            if ref is None:
                continue
            key = (
                getattr(ref, "source_id", None),
                _source_type_value(ref),
                getattr(ref, "metric_name", None),
                getattr(ref, "section_id", None),
                getattr(ref, "document_id", None),
                str(getattr(ref, "url", None)),
                getattr(ref, "period_role", None),
            )
            entry = rows.setdefault(
                key,
                {
                    "source_id": getattr(ref, "source_id", "source"),
                    "type": _source_type_value(ref),
                    "locator": _locator(ref),
                    "title": getattr(ref, "title", None) or getattr(ref, "source_id", "source"),
                    "url": str(getattr(ref, "url", "") or ""),
                    "timing": source_timing_label(ref),
                    "period_role": getattr(ref, "period_role", None),
                    "used_for": set[str](),
                },
            )
            entry["used_for"].add(f"{agent}: {getattr(item, 'summary', '')[:80]}")

    if not rows:
        return ["No source references were emitted."]

    lines = [
        "| source_id | type | locator | title | period_role | timing | used for | source/location |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for entry in rows.values():
        used_for = "; ".join(sorted(entry["used_for"]))
        lines.append(
            (
                "| `{source_id}` | {type} | {locator} | {title} | {period_role} | "
                "{timing} | {used_for} | {source_location} |"
            ).format(
                source_id=escape_md_table(entry["source_id"]),
                type=escape_md_table(entry["type"]),
                locator=escape_md_table(entry["locator"]),
                title=escape_md_table(entry["title"]),
                period_role=escape_md_table(entry["period_role"]),
                timing=escape_md_table(entry["timing"]),
                used_for=escape_md_table(used_for),
                source_location=escape_md_table(_url_or_locator(entry)),
            )
        )
    return lines
