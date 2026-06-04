"""Missing-data rendering and confidence caps."""

from __future__ import annotations

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

BLOCKING_MISSING_PATTERNS = (
    "blocking missing data",
    "insufficient evidence",
    "cannot determine",
    "required source",
)

STRUCTURAL_NON_ACQUIRED_PATTERNS = (
    "revenue consensus",
    "consensus_for_guided_period",
    "guided-period consensus",
    "guided period consensus",
    "source-backed guided-period consensus",
    "guided-period metric",
    "guided period metric",
    "guidance range",
    "prior guidance track record",
)

YFINANCE_EXPECTED_METRICS = (
    ("eps", "eps actual"),
    ("eps_consensus", "eps consensus"),
    ("revenue", "reported revenue"),
    ("operating_cash_flow", "operating cash flow"),
    ("free_cash_flow", "free cash flow"),
    ("capex", "capex"),
)


def _findings(brief) -> list:
    return [
        getattr(brief, "earnings_quality_finding", None),
        getattr(brief, "cash_flow_risk_finding", None),
        getattr(brief, "management_intent_finding", None),
        getattr(brief, "guidance_finding", None),
    ]


def collect_missing_data(brief) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for finding in _findings(brief):
        if finding is None:
            continue
        agent = getattr(finding, "agent_name", "UnknownAgent")
        for item in getattr(finding, "missing_data", []) or []:
            text = str(item)
            lowered = text.lower()
            if any(p in lowered for p in STRUCTURAL_NON_ACQUIRED_PATTERNS):
                severity = "structural_non_acquired"
            elif any(p in lowered for p in BLOCKING_MISSING_PATTERNS):
                severity = "blocking_missing_data"
            elif any(p in lowered for p in IMPORTANT_MISSING_PATTERNS):
                severity = "material_caveat"
            else:
                severity = "non_blocking"
            rows.append((agent, severity, text))
    return rows


def missing_data_lines(
    brief,
    decision=None,
    metrics=None,
    *,
    include_structural: bool = False,
) -> list[str]:
    rows = collect_missing_data(brief)
    if not include_structural:
        rows = [row for row in rows if row[1] != "structural_non_acquired"]
    provider_row = _provider_expected_missing_row(metrics)
    if provider_row is not None:
        rows.append(provider_row)
    if not rows:
        return ["- No reportable missing-data caveats were emitted by specialist agents."]
    lines = ["| Agent | Severity | Missing data / confidence limit |", "|---|---|---|"]
    for agent, severity, text in rows:
        safe = text.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {agent} | {severity} | {safe} |")
    return lines


def confidence_cap(brief, decision=None, metrics=None) -> tuple[float, list[str]]:
    cap = 1.0
    reasons: list[str] = []
    rows = collect_missing_data(brief)
    provider_missing = collect_expected_provider_missing(metrics)
    if metrics is None:
        blocking_count = sum(1 for _, severity, _ in rows if severity == "blocking_missing_data")
        material_count = sum(1 for _, severity, _ in rows if severity == "material_caveat")
    else:
        blocking_count = 0
        material_count = len(provider_missing)
    if blocking_count:
        cap = min(cap, 0.25)
        reasons.append("blocking missing data")
    if material_count:
        missing_ratio = min(material_count, 3) / 3
        cap = min(cap, 1.0 - ((1.0 - 0.40) * missing_ratio))
        reasons.append(_material_caveat_reason(metrics, provider_missing))

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


def collect_expected_provider_missing(metrics) -> list[str]:
    if metrics is None:
        return []
    provider_value = _source_provider_value(metrics)
    if provider_value not in {"yfinance", "sec"}:
        return []
    missing: list[str] = []
    for field_name, label in YFINANCE_EXPECTED_METRICS:
        if getattr(metrics, field_name, None) is None:
            missing.append(label)
    return missing


def _source_provider_value(metrics) -> str:
    provider = getattr(metrics, "source_provider", None)
    return str(getattr(provider, "value", provider or "")).lower()


def _provider_expected_missing_row(metrics) -> tuple[str, str, str] | None:
    provider_missing = collect_expected_provider_missing(metrics)
    if not provider_missing:
        return None
    provider_value = _source_provider_value(metrics)
    if provider_value == "sec":
        message = "SEC fallback did not provide yfinance-expected fields: " + ", ".join(
            provider_missing
        )
    else:
        message = "yfinance did not provide expected fields: " + ", ".join(provider_missing)
    return ("Workflow", "provider_expected_missing", message)


def _material_caveat_reason(metrics, provider_missing: list[str]) -> str:
    if provider_missing:
        if _source_provider_value(metrics) == "sec":
            return "SEC fallback missing yfinance-expected data: " + ", ".join(provider_missing)
        return "missing expected yfinance data: " + ", ".join(provider_missing)
    return "multiple material caveats"


def apply_confidence_caps(decision, brief, metrics=None):
    cap, reasons = confidence_cap(brief, decision, metrics)
    current = float(getattr(decision, "confidence", 0.0) or 0.0)
    updates = {}
    if current > cap:
        updates["confidence"] = cap
    if "blocking missing data" in reasons:
        from .workflow_models import VerdictLabel

        updates["verdict"] = VerdictLabel.INSUFFICIENT_EVIDENCE
        updates.setdefault("confidence", min(current, cap))
    if not updates:
        return decision
    if hasattr(decision, "model_copy"):
        return decision.model_copy(update=updates)
    for key, value in updates.items():
        setattr(decision, key, value)
    return decision
