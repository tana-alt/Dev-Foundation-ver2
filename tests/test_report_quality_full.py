from types import SimpleNamespace

import pytest

from src.report_quality_contracts import (
    ExternalResearchPacket,
    ExternalSourceCandidate,
    SourceTiming,
)
from src.report_quality_evidence_matrix import evidence_matrix_lines
from src.report_quality_external_research import render_external_sources_markdown
from src.report_quality_guidance import (
    GuidanceAcquisitionError,
    GuidanceStatus,
    classify_guidance_sources,
    validate_guidance_required,
)
from src.report_quality_missing_data import confidence_cap, missing_data_lines
from src.report_quality_numeric_grounding import (
    NumericGroundingError,
    apply_numeric_grounding_caveats,
    validate_numeric_grounding,
)
from src.report_quality_source_inventory import source_inventory_lines
from src.report_quality_source_timing import classify_source_timing
from src.workflow_models import SourceRef, SourceType


def ref(source_id="filing:other", source_type="filing", metric_name=None):
    return SimpleNamespace(
        source_id=source_id,
        source_type=SimpleNamespace(value=source_type),
        title="source title",
        url="https://example.com/source",
        document_id="doc",
        section_id="section",
        metric_name=metric_name,
    )


def evidence(
    summary="Revenue growth was strong",
    detail="Revenue was $10 billion.",
    value=None,
    metric_name=None,
):
    return SimpleNamespace(
        evidence_id="ev1",
        polarity=SimpleNamespace(value="positive"),
        summary=summary,
        detail=detail,
        source_ref=ref(metric_name=metric_name),
        metric_name=metric_name,
        value=value,
        unit="USD" if value is not None else None,
        confidence=0.9,
    )


def finding(name="GuidanceAnalyst", missing=None, key=None, counter=None):
    return SimpleNamespace(
        agent_name=name,
        missing_data=missing or [],
        key_evidence=key or [],
        counter_evidence=counter or [],
    )


def brief(**kwargs):
    defaults = {
        "earnings_quality_finding": finding("EarningsQualityAnalyst"),
        "cash_flow_risk_finding": finding("CashFlowRiskAnalyst"),
        "management_intent_finding": finding("ManagementIntentAnalyst"),
        "guidance_finding": finding("GuidanceAnalyst"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_guidance_gate_accepts_metrics_guidance(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_GUIDANCE", raising=False)
    metrics = SimpleNamespace(
        guidance="Next-quarter revenue outlook is approximately $10B.", source_refs=[]
    )
    fact = validate_guidance_required(metrics, [])
    assert fact.status == "found"


def test_guidance_gate_rejects_missing_guidance(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_GUIDANCE", raising=False)
    metrics = SimpleNamespace(guidance=None, source_refs=[])
    sections = [SimpleNamespace(heading="Revenue", text="Revenue increased.", source_ref=ref())]
    with pytest.raises(GuidanceAcquisitionError):
        validate_guidance_required(metrics, sections)


def test_guidance_classification_finds_body_guidance_under_generic_heading():
    metrics = SimpleNamespace(guidance=None, source_refs=[])
    source_ref = SourceRef(
        source_id="deck:p4:section-1",
        source_type=SourceType.EARNINGS_PRESENTATION,
        document_id="deck",
        section_id="deck:p4:section-1",
        page=4,
        title="Investor presentation",
    )
    section = SimpleNamespace(
        section_id="deck:p4:section-1",
        heading="Investor presentation page 4",
        text="Q2 FY2027 outlook: revenue is expected to be approximately $28 billion.",
        source_ref=source_ref,
    )

    fact = classify_guidance_sources(metrics, [section])

    assert fact.status is GuidanceStatus.FOUND
    assert fact.confidence >= 0.75
    assert fact.source_refs == [source_ref]
    assert fact.candidate_section_ids == ["deck:p4:section-1"]
    assert fact.matched_signal_strength == "strong"
    assert "outlook" in fact.matched_terms


def test_guidance_classification_keeps_forward_looking_only_signal_weak():
    metrics = SimpleNamespace(guidance=None, source_refs=[])
    source_ref = SourceRef(
        source_id="deck:p9:section-1",
        source_type=SourceType.EARNINGS_PRESENTATION,
        document_id="deck",
        section_id="deck:p9:section-1",
        page=9,
        title="Investor presentation",
    )
    section = SimpleNamespace(
        section_id="deck:p9:section-1",
        heading="Legal disclaimer",
        text="Forward-looking statements are subject to risks and uncertainties.",
        source_ref=source_ref,
    )

    fact = classify_guidance_sources(metrics, [section])

    assert fact.status is GuidanceStatus.AMBIGUOUS
    assert fact.confidence < 0.5
    assert fact.source_refs == [source_ref]
    assert fact.candidate_section_ids == ["deck:p9:section-1"]
    assert fact.matched_signal_strength == "weak"
    assert "forward-looking statements" in fact.matched_terms


def test_evidence_matrix_renders_value_and_source():
    rendered = "\n".join(evidence_matrix_lines([evidence(value=2.09, metric_name="eps_consensus")]))
    assert "2.09 USD" in rendered
    assert "filing:other" in rendered
    assert "same_period_primary" in rendered


def test_numeric_grounding_rejects_material_claim_without_number(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", raising=False)
    item = evidence(
        summary="Revenue growth was strong",
        detail="Revenue growth was strong.",
        value=None,
        metric_name=None,
    )
    with pytest.raises(NumericGroundingError):
        validate_numeric_grounding([item])


def test_numeric_grounding_accepts_explicit_missing_data_caveat(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", raising=False)
    item = evidence(
        summary="FCF improvement is unclear because direct FCF metrics are absent.",
        detail="FCF improvement is unclear because direct FCF metrics are not available.",
        value=None,
        metric_name=None,
    )

    validate_numeric_grounding([item])


def test_numeric_grounding_caveat_repairs_material_claim_without_number(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", raising=False)
    item = evidence(
        summary="Revenue growth was strong",
        detail="Revenue growth was strong.",
        value=None,
        metric_name=None,
    )

    repaired, warnings = apply_numeric_grounding_caveats([item])

    assert warnings
    assert "ev1" in warnings[0]
    assert "not routed" in repaired[0].detail
    assert repaired[0].confidence < item.confidence
    validate_numeric_grounding(repaired)


def test_source_timing_primary_source():
    assert classify_source_timing(ref()).value == "same_period_primary"


def test_missing_data_confidence_cap_material_caveat():
    b = brief(
        guidance_finding=finding("GuidanceAnalyst", missing=["guidance metrics were not routed"])
    )
    cap, reasons = confidence_cap(b)
    assert cap <= 0.60
    assert reasons
    assert "guidance" in "\n".join(missing_data_lines(b)).lower()


def test_confidence_cap_steps_down_with_more_material_caveats():
    one = brief(guidance_finding=finding("GuidanceAnalyst", missing=["guidance is missing"]))
    many = brief(
        earnings_quality_finding=finding(
            "EarningsQualityAnalyst", missing=["consensus is missing"]
        ),
        cash_flow_risk_finding=finding("CashFlowRiskAnalyst", missing=["FCF is missing"]),
        guidance_finding=finding("GuidanceAnalyst", missing=["guidance is missing"]),
    )

    one_cap, _ = confidence_cap(one)
    many_cap, reasons = confidence_cap(many)

    assert many_cap < one_cap
    assert "multiple material caveats" in reasons


def test_confidence_cap_flags_blocking_missing_data():
    b = brief(
        guidance_finding=finding(
            "GuidanceAnalyst",
            missing=["blocking missing data: required source unavailable for reported EPS"],
        )
    )

    cap, reasons = confidence_cap(b)

    assert cap <= 0.25
    assert "blocking missing data" in reasons


def test_missing_data_lines_hide_structural_non_acquired_items_by_default():
    b = brief(
        guidance_finding=finding(
            "GuidanceAnalyst",
            missing=[
                "No revenue consensus was routed, so revenue beat/miss cannot be stated as a fact.",
                "consensus_for_guided_period is null, preventing a direct assessment of guidance.",
            ],
        )
    )

    visible = "\n".join(missing_data_lines(b))
    internal = "\n".join(missing_data_lines(b, include_structural=True))

    assert "revenue consensus" not in visible
    assert "consensus_for_guided_period" not in visible
    assert "revenue consensus" in internal
    assert "consensus_for_guided_period" in internal


def test_missing_data_lines_hide_structural_rows_when_metrics_supplied():
    b = brief(
        guidance_finding=finding(
            "GuidanceAnalyst",
            missing=[
                "No revenue consensus was routed, so revenue beat/miss cannot be stated as a fact.",
                "consensus_for_guided_period is null, preventing a direct assessment of guidance.",
            ],
        )
    )
    metrics = SimpleNamespace(
        source_provider="manual",
        eps=None,
        eps_consensus=None,
        revenue=81_615_000_000.0,
        operating_cash_flow=None,
        free_cash_flow=None,
        capex=None,
    )

    visible = "\n".join(missing_data_lines(b, metrics=metrics))

    assert "revenue consensus" not in visible
    assert "consensus_for_guided_period" not in visible
    assert "provider_expected_missing" not in visible


def test_confidence_cap_ignores_structural_non_acquired_consensus_when_metrics_supplied():
    b = brief(
        guidance_finding=finding(
            "GuidanceAnalyst",
            missing=[
                "No revenue consensus was routed, so revenue beat/miss cannot be stated as a fact.",
                "consensus_for_guided_period is null, preventing a direct assessment of guidance.",
            ],
        )
    )
    metrics = SimpleNamespace(
        source_provider="yfinance",
        eps=1.87,
        eps_consensus=1.77,
        revenue=81_615_000_000.0,
        operating_cash_flow=50_344_000_000.0,
        free_cash_flow=48_587_000_000.0,
        capex=-1_757_000_000.0,
    )

    _, reasons = confidence_cap(b, metrics=metrics)

    assert not any("revenue consensus" in reason for reason in reasons)
    assert not any("guided" in reason for reason in reasons)
    assert not any("material caveats" in reason for reason in reasons)


def test_confidence_cap_counts_missing_expected_yfinance_data_only():
    b = SimpleNamespace()
    metrics = SimpleNamespace(
        source_provider="yfinance",
        eps=1.87,
        eps_consensus=None,
        revenue=81_615_000_000.0,
        operating_cash_flow=50_344_000_000.0,
        free_cash_flow=48_587_000_000.0,
        capex=-1_757_000_000.0,
    )

    cap, reasons = confidence_cap(b, metrics=metrics)

    assert cap == pytest.approx(0.80)
    assert reasons
    assert "eps consensus" in "\n".join(reasons)
    rendered = "\n".join(missing_data_lines(b, metrics=metrics))
    assert "provider_expected_missing" in rendered
    assert "yfinance did not provide expected fields: eps consensus" in rendered


def test_confidence_cap_uses_missing_ratio_with_three_missing_max():
    metrics = SimpleNamespace(
        source_provider="yfinance",
        eps=None,
        eps_consensus=None,
        revenue=81_615_000_000.0,
        operating_cash_flow=50_344_000_000.0,
        free_cash_flow=48_587_000_000.0,
        capex=-1_757_000_000.0,
    )

    cap, _ = confidence_cap(SimpleNamespace(), metrics=metrics)

    assert cap == pytest.approx(0.60)


def test_sec_fallback_missing_expected_yfinance_data_caps_and_renders_provider_gap():
    b = SimpleNamespace()
    metrics = SimpleNamespace(
        source_provider="sec",
        eps=None,
        eps_consensus=None,
        revenue=81_615_000_000.0,
        operating_cash_flow=None,
        free_cash_flow=None,
        capex=None,
    )

    cap, reasons = confidence_cap(b, metrics=metrics)
    rendered = "\n".join(missing_data_lines(b, metrics=metrics))

    assert cap == pytest.approx(0.40)
    assert "SEC fallback missing yfinance-expected data" in "\n".join(reasons)
    assert "eps actual" in "\n".join(reasons)
    assert "Workflow | provider_expected_missing" in rendered
    assert "SEC fallback did not provide yfinance-expected fields" in rendered
    assert "reported revenue" not in rendered


def test_source_inventory_uses_local_locator_for_non_url_sources():
    financial_ref = SimpleNamespace(
        source_id="yfinance:NVDA:2025Q3:eps_consensus",
        source_type=SimpleNamespace(value="financial_api"),
        title="Yahoo Finance via yfinance",
        url=None,
        document_id=None,
        section_id=None,
        metric_name="eps_consensus",
        period_role="consensus_for_reported_period",
    )
    presentation_ref = SimpleNamespace(
        source_id="deck:p4:section-1",
        source_type=SimpleNamespace(value="earnings_presentation"),
        title="FY2025 Q3 earnings presentation",
        url=None,
        document_id="deck",
        section_id="deck:p4:section-1",
        metric_name="revenue_guidance",
        period_role="guided_period",
    )
    b = brief(
        guidance_finding=finding(
            "GuidanceAnalyst",
            key=[
                evidence(metric_name="eps_consensus"),
                SimpleNamespace(
                    summary="Guidance revenue was disclosed.",
                    source_ref=presentation_ref,
                ),
            ],
        )
    )
    b.guidance_finding.key_evidence[0].source_ref = financial_ref

    rendered = "\n".join(source_inventory_lines(b))

    assert "Yahoo Finance via yfinance" in rendered
    assert "deck:p4:section-1" in rendered
    assert "consensus_for_reported_period" in rendered
    assert "guided_period" in rendered
    assert "no URL" not in rendered


def test_external_sources_render_separate_appendix():
    packet = ExternalResearchPacket(
        ticker="NVDA",
        fiscal_period="2027Q1",
        candidates=[
            ExternalSourceCandidate(
                source_id="external:news:1",
                title="Example",
                url="https://example.com",
                timing=SourceTiming.POST_EVENT_EXTERNAL,
                proposed_use="Context only",
            )
        ],
    )
    rendered = render_external_sources_markdown(packet)
    assert "Interactive External Sources" in rendered
    assert "post_event_external" in rendered
    assert "false" in rendered
