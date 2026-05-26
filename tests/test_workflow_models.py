import pytest
from pydantic import ValidationError

from src.workflow_models import (
    AgentRole,
    AgentTeam,
    AgentResult,
    AnalysisBrief,
    DebateResult,
    EvidenceItem,
    EvidencePolarity,
    FinancialMetrics,
    ImpactArea,
    JudgeDecision,
    ReviewRequest,
    ReviewResponse,
    SourceRef,
    SourceType,
    StepState,
    StepStatus,
    VerdictLabel,
    WorkflowStep,
)


def financial_source(metric_name: str = "eps") -> SourceRef:
    return SourceRef(
        source_id="api:eps:2025Q3",
        source_type=SourceType.FINANCIAL_API,
        metric_name=metric_name,
        title="Financial API",
    )


def filing_source() -> SourceRef:
    return SourceRef(
        source_id="filing:10q:item2",
        source_type=SourceType.FILING,
        document_id="10q-2025q3",
        section_id="item2",
        page=14,
        line_start=10,
        line_end=12,
    )


def evidence(
    evidence_id: str = "ev:positive:eps",
    polarity: EvidencePolarity = EvidencePolarity.POSITIVE,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        polarity=polarity,
        summary="EPS exceeded consensus.",
        detail="Adjusted EPS was above consensus and operating margin improved.",
        impact_areas=[ImpactArea.EPS],
        source_ref=financial_source("eps"),
        metric_name="eps",
        value=1.23,
        unit="USD/share",
        confidence=0.8,
    )


def completed_status(step: WorkflowStep) -> StepStatus:
    return StepStatus(step=step, state=StepState.COMPLETED)


def test_financial_metrics_normalizes_ticker_and_currency():
    metrics = FinancialMetrics(ticker=" nvda ", fiscal_period="2025Q3", currency=" usd ")

    assert metrics.ticker == "NVDA"
    assert metrics.currency == "USD"


def test_contracts_reject_extra_fields_and_strip_strings():
    source = SourceRef(
        source_id=" filing:press ",
        source_type="press_release",
        url="https://example.com/release",
        title="  Q3 release  ",
    )

    assert source.source_id == "filing:press"
    assert source.title == "Q3 release"

    with pytest.raises(ValidationError):
        SourceRef(
            source_id="api:eps",
            source_type="financial_api",
            metric_name="eps",
            unexpected="not allowed",
        )


def test_source_ref_requires_financial_metric_name():
    with pytest.raises(ValidationError):
        SourceRef(source_id="api:missing", source_type="financial_api")


def test_source_ref_rejects_invalid_line_range():
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="filing:bad-lines",
            source_type="filing",
            document_id="10q",
            line_start=20,
            line_end=10,
        )


def test_review_request_validates_embedded_metrics_match_request():
    with pytest.raises(ValidationError):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(ticker="AMD", fiscal_period="2025Q3"),
        )


def test_verdict_label_is_lowercase_enum():
    decision_args = {
        "verdict": "GOOD",
        "confidence": 0.7,
        "summary": "Strong quarter.",
        "rationale": "Positive evidence outweighed risks.",
        "positive_evidence": [evidence()],
        "negative_evidence": [evidence("ev:negative:capex", EvidencePolarity.NEGATIVE)],
        "eps_outlook": "EPS may improve if margin strength persists.",
        "fcf_outlook": "FCF may improve after investment intensity normalizes.",
    }

    with pytest.raises(ValidationError):
        JudgeDecision(**decision_args)

    decision_args["verdict"] = "good"
    decision = JudgeDecision(**decision_args)

    assert decision.verdict == VerdictLabel.GOOD


def test_judge_decision_requires_positive_and_negative_evidence():
    with pytest.raises(ValidationError):
        JudgeDecision(
            verdict="neutral",
            confidence=0.6,
            summary="Mixed quarter.",
            rationale="Growth improved, but cash conversion remained pressured.",
            positive_evidence=[],
            negative_evidence=[evidence("ev:negative:fcf", EvidencePolarity.NEGATIVE)],
            eps_outlook="EPS path is balanced.",
            fcf_outlook="FCF path is uncertain.",
        )


def test_full_review_response_contains_structured_result_and_markdown():
    positive = evidence()
    negative = evidence("ev:negative:capex", EvidencePolarity.NEGATIVE)
    status = completed_status(WorkflowStep.JUDGE)
    agent_result = AgentResult(
        agent_role=AgentRole.EPS_ANALYST,
        team=AgentTeam.FINANCIAL,
        status=status,
        headline="EPS beat was operating-supported.",
        conclusion="Margin expansion supported the EPS beat.",
        key_evidence=[positive],
        counter_evidence=[negative],
        confidence=0.75,
    )
    brief = AnalysisBrief(
        ticker="NVDA",
        fiscal_period="2025Q3",
        financial_agent_results=[agent_result],
        positive_evidence_pool=[positive],
        negative_evidence_pool=[negative],
        synthesis="Evidence is positive, but cash-flow timing remains a counterpoint.",
    )
    debate = DebateResult(
        bull_case="EPS quality and guidance support a good interpretation.",
        bear_case="Higher CapEx pressures near-term FCF.",
        risk_case="Demand concentration could weaken the setup.",
        evaluation="Bull case is stronger, with material risks.",
        strongest_positive_evidence=[positive],
        strongest_negative_evidence=[negative],
    )
    decision = JudgeDecision(
        verdict="good",
        confidence=0.72,
        summary="Strong quarter with cash-flow caveats.",
        rationale="EPS and margin evidence outweighed near-term FCF pressure.",
        positive_evidence=[positive],
        negative_evidence=[negative],
        eps_outlook="EPS can rise if margin expansion persists.",
        fcf_outlook="FCF can improve if CapEx intensity moderates.",
    )

    response = ReviewResponse(
        request_id="req-1",
        ticker="nvda",
        fiscal_period="2025Q3",
        steps=[status],
        analysis_brief=brief,
        debate_result=debate,
        judge_decision=decision,
        markdown_report="# Earnings Review\n\nVerdict: good",
    )

    assert response.ticker == "NVDA"
    assert response.markdown_report.startswith("# Earnings Review")
    assert response.is_investment_advice is False
