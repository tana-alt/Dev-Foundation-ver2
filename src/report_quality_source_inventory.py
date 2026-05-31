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
                str(
                    getattr(
                        getattr(ref, "source_type", None), "value", getattr(ref, "source_type", "")
                    )
                ),
                getattr(ref, "metric_name", None),
                getattr(ref, "section_id", None),
                getattr(ref, "document_id", None),
                str(getattr(ref, "url", None)),
            )
            entry = rows.setdefault(
                key,
                {
                    "source_id": getattr(ref, "source_id", "source"),
                    "type": str(
                        getattr(
                            getattr(ref, "source_type", None),
                            "value",
                            getattr(ref, "source_type", ""),
                        )
                    ),
                    "locator": getattr(ref, "metric_name", None)
                    or getattr(ref, "section_id", None)
                    or getattr(ref, "document_id", None)
                    or "source",
                    "title": getattr(ref, "title", None) or getattr(ref, "source_id", "source"),
                    "url": str(getattr(ref, "url", "") or ""),
                    "timing": source_timing_label(ref),
                    "used_for": set[str](),
                },
            )
            entry["used_for"].add(f"{agent}: {getattr(item, 'summary', '')[:80]}")

    if not rows:
        return ["No source references were emitted."]

    lines = [
        "| source_id | type | locator | title | timing | used for | url |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in rows.values():
        used_for = "; ".join(sorted(entry["used_for"]))
        lines.append(
            "| `{source_id}` | {type} | {locator} | {title} | {timing} | {used_for} | {url} |".format(
                source_id=escape_md_table(entry["source_id"]),
                type=escape_md_table(entry["type"]),
                locator=escape_md_table(entry["locator"]),
                title=escape_md_table(entry["title"]),
                timing=escape_md_table(entry["timing"]),
                used_for=escape_md_table(used_for),
                url=escape_md_table(entry["url"] or "no URL"),
            )
        )
    return lines
