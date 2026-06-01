from datetime import date
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
from src.report_quality_source_timing import classify_source_timing, source_timing_label
from src.workflow_models import (
    EvidenceItem,
    EvidencePolarity,
    ImpactArea,
    MissingDataItem,
    SourceRef,
    SourceType,
)
from src.workflow_validation import WorkflowValidationError, WorkflowValidationGate


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


def test_numeric_grounding_rejects_period_numbers_without_metric_value(monkeypatch):
    monkeypatch.delenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", raising=False)
    item = evidence(
        summary="Revenue growth improved in fiscal 2025 Q3.",
        detail="Revenue growth improved during fiscal 2025 Q3 without a revenue amount or percentage.",
        value=None,
        metric_name=None,
    )

    with pytest.raises(NumericGroundingError):
        validate_numeric_grounding([item])


def test_source_validity_rejects_reused_source_id_with_different_locator():
    validator = WorkflowValidationGate()
    canonical = SourceRef(
        source_id="filing:segments",
        source_type=SourceType.FILING,
        document_id="10q",
        section_id="segments",
        title="Segment note",
    )
    emitted = EvidenceItem(
        evidence_id="ev-source-mismatch",
        polarity=EvidencePolarity.POSITIVE,
        summary="Segment margin improved.",
        detail="Segment margin improved by 120 bps.",
        impact_areas=[ImpactArea.OVERALL],
        source_ref=SourceRef(
            source_id="filing:segments",
            source_type=SourceType.FILING,
            document_id="10q",
            section_id="liquidity",
            title="Segment note",
        ),
        confidence=0.7,
    )

    with pytest.raises(WorkflowValidationError, match="mismatched locator"):
        validator.validate_evidence_sources([emitted], {validator.source_signature(canonical)})


def test_source_validity_rejects_reused_source_id_with_different_url():
    validator = WorkflowValidationGate()
    canonical = SourceRef(
        source_id="filing:liquidity",
        source_type=SourceType.FILING,
        document_id="10q",
        section_id="liquidity",
        title="Liquidity note",
        url="https://example.com/10q#liquidity",
    )
    emitted = EvidenceItem(
        evidence_id="ev-url-mismatch",
        polarity=EvidencePolarity.NEGATIVE,
        summary="Debt pressure rose.",
        detail="Debt pressure rose by 80 bps.",
        impact_areas=[ImpactArea.OVERALL],
        source_ref=SourceRef(
            source_id="filing:liquidity",
            source_type=SourceType.FILING,
            document_id="10q",
            section_id="liquidity",
            title="Liquidity note",
            url="https://example.com/10q#different-section",
        ),
        confidence=0.7,
    )

    with pytest.raises(WorkflowValidationError, match="mismatched locator"):
        validator.validate_evidence_sources([emitted], {validator.source_signature(canonical)})


def test_source_timing_primary_source():
    assert classify_source_timing(ref()).value == "same_period_primary"


def test_source_timing_label_uses_candidate_timing():
    candidate = ExternalSourceCandidate(
        source_id="external:news:2",
        title="Post-event article",
        url="https://example.com/news",
        timing=SourceTiming.POST_EVENT_EXTERNAL,
        proposed_use="Context only",
    )

    assert source_timing_label(candidate) == "post_event_external"


def test_source_timing_unknown_candidate_uses_dates_when_available():
    candidate = ExternalSourceCandidate(
        source_id="external:news:3",
        title="Post-event article",
        url="https://example.com/news",
        published_date=date(2025, 2, 20),
        related_event_date=date(2025, 2, 1),
        timing=SourceTiming.UNKNOWN,
        proposed_use="Context only",
    )

    assert (
        source_timing_label(candidate, event_date=candidate.related_event_date)
        == "post_event_external"
    )


def test_missing_data_confidence_cap_material_caveat():
    b = brief(
        guidance_finding=finding("GuidanceAnalyst", missing=["guidance metrics were not routed"])
    )
    cap, reasons = confidence_cap(b)
    assert cap <= 0.60
    assert reasons
    assert "guidance" in "\n".join(missing_data_lines(b)).lower()


def test_missing_data_items_cap_blocking_report_matrix_gap():
    b = brief()
    matrix_gaps = [
        MissingDataItem(
            missing_data_id="missing:fcf-bridge",
            topic="FCF bridge",
            reason="The source set does not include a cash conversion bridge.",
            materiality="high",
            requested_source_type=SourceType.FILING,
            blocks_verdict=True,
        )
    ]

    cap, reasons = confidence_cap(b, missing_data_items=matrix_gaps)
    rendered = "\n".join(missing_data_lines(b, missing_data_items=matrix_gaps))

    assert cap <= 0.45
    assert "blocking missing data" in reasons
    assert "FCF bridge" in rendered
    assert "blocking_gap" in rendered


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
