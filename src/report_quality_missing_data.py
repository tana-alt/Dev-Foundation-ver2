"""Missing-data rendering and confidence caps."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

IMPORTANT_MISSING_PATTERNS = (
    "guidance",
    "cash flow",
    "fcf",
    "capex",
    "working capital",
    "eps bridge",
    "consensus",
    "source",
)


def _findings(brief) -> list:
    return [
        getattr(brief, "earnings_quality_finding", None),
        getattr(brief, "cash_flow_risk_finding", None),
        getattr(brief, "management_intent_finding", None),
        getattr(brief, "guidance_finding", None),
    ]


def collect_missing_data(
    brief: Any,
    *,
    missing_data_items: Iterable[Any] | None = None,
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    matrix_missing_data = (
        missing_data_items
        if missing_data_items is not None
        else getattr(brief, "missing_data_items", []) or []
    )
    for item in matrix_missing_data:
        materiality = str(getattr(item, "materiality", "") or "").lower()
        blocks_verdict = bool(getattr(item, "blocks_verdict", False))
        if blocks_verdict:
            severity = "blocking_gap"
        elif materiality in {"high", "medium"}:
            severity = "material_caveat"
        else:
            severity = "non_blocking"

        topic = str(getattr(item, "topic", "Missing data") or "Missing data")
        reason = str(getattr(item, "reason", "") or "").strip()
        requested = getattr(item, "requested_source_type", None)
        requested_value = getattr(requested, "value", requested)
        requested_text = f" Requested source: {requested_value}." if requested_value else ""
        rows.append(("ReportMatrix", severity, f"{topic}: {reason}{requested_text}".strip()))

    for finding in _findings(brief):
        if finding is None:
            continue
        agent = getattr(finding, "agent_name", "UnknownAgent")
        for item in getattr(finding, "missing_data", []) or []:
            text = str(item)
            severity = (
                "material_caveat"
                if any(p in text.lower() for p in IMPORTANT_MISSING_PATTERNS)
                else "non_blocking"
            )
            rows.append((agent, severity, text))
    return rows


def missing_data_lines(
    brief: Any,
    decision: Any = None,
    *,
    missing_data_items: Iterable[Any] | None = None,
) -> list[str]:
    rows = collect_missing_data(brief, missing_data_items=missing_data_items)
    if not rows:
        return ["- No material missing-data caveats were emitted by specialist agents."]
    lines = ["| Agent | Severity | Missing data / confidence limit |", "|---|---|---|"]
    for agent, severity, text in rows:
        safe = text.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {agent} | {severity} | {safe} |")
    return lines


def confidence_cap(
    brief: Any,
    decision: Any = None,
    *,
    missing_data_items: Iterable[Any] | None = None,
) -> tuple[float, list[str]]:
    cap = 1.0
    reasons: list[str] = []
    rows = collect_missing_data(brief, missing_data_items=missing_data_items)
    if any(severity == "blocking_gap" for _, severity, _ in rows):
        cap = min(cap, 0.45)
        reasons.append("blocking missing data")
    if any(severity == "material_caveat" for _, severity, _ in rows):
        cap = min(cap, 0.60)
        reasons.append("important missing data")

    source_types = set()
    has_counter = True
    for finding in _findings(brief):
        if finding is None:
            continue
        if not getattr(finding, "counter_evidence", None):
            has_counter = False
        for item in [
            *(getattr(finding, "key_evidence", []) or []),
            *(getattr(finding, "counter_evidence", []) or []),
        ]:
            ref = getattr(item, "source_ref", None)
            if ref is not None:
                source_types.add(
                    str(
                        getattr(
                            getattr(ref, "source_type", None),
                            "value",
                            getattr(ref, "source_type", ""),
                        )
                    )
                )

    if len(source_types) == 1:
        cap = min(cap, 0.65)
        reasons.append("one source type only")
    if not has_counter:
        cap = min(cap, 0.60)
        reasons.append("missing counter evidence")
    return cap, reasons


def apply_confidence_caps(
    decision: Any,
    brief: Any,
    *,
    missing_data_items: Iterable[Any] | None = None,
):
    cap, _ = confidence_cap(brief, decision, missing_data_items=missing_data_items)
    current = float(getattr(decision, "confidence", 0.0) or 0.0)
    if current <= cap:
        return decision
    if hasattr(decision, "model_copy"):
        return decision.model_copy(update={"confidence": cap})
    return decision
