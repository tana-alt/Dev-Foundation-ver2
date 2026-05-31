from types import SimpleNamespace

import pytest

from src.report_quality_contracts import (
    ExternalResearchPacket,
    ExternalSourceCandidate,
    SourceTiming,
)
from src.report_quality_evidence_matrix import evidence_matrix_lines
from src.report_quality_external_research import render_external_sources_markdown
from src.report_quality_guidance import GuidanceAcquisitionError, validate_guidance_required
from src.report_quality_missing_data import confidence_cap, missing_data_lines
from src.report_quality_numeric_grounding import NumericGroundingError, validate_numeric_grounding
from src.report_quality_source_timing import classify_source_timing


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
