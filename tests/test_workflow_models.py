import pytest
from pydantic import ValidationError

from src.workflow_models import (
    AgentResult,
    AgentRole,
    AgentTeam,
    AnalysisBrief,
    BearCase,
    BullCase,
    CashFlowRiskFinding,
    DebateResult,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FinalVerdict,
    FinancialMetrics,
    FindingCoverage,
    GuidanceFinding,
    ImpactArea,
    JudgeDecision,
    ManagementIntentFinding,
    MetricStoreEntry,
    PresentationMetricHint,
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


def specialist_finding(agent_name: str):
    positive = evidence(f"ev:positive:{agent_name.lower()}")
    negative = evidence(f"ev:negative:{agent_name.lower()}", EvidencePolarity.NEGATIVE)
    finding_args = {
        "stance": "mixed",
        "summary": f"{agent_name} found mixed evidence.",
        "key_evidence": [positive],
        "counter_evidence": [negative],
        "confidence": 0.7,
        "handoff_summary": f"{agent_name} handoff.",
    }
    finding_classes = {
        "EarningsQualityAnalyst": EarningsQualityFinding,
        "CashFlowRiskAnalyst": CashFlowRiskFinding,
        "ManagementIntentAnalyst": ManagementIntentFinding,
        "GuidanceAnalyst": GuidanceFinding,
    }
    return finding_classes[agent_name](**finding_args)


def analysis_brief(
    positive: EvidenceItem | None = None,
    negative: EvidenceItem | None = None,
    financial_agent_results: list[AgentResult] | None = None,
) -> AnalysisBrief:
    positive = positive or evidence()
    negative = negative or evidence("ev:negative:capex", EvidencePolarity.NEGATIVE)
    return AnalysisBrief(
        ticker="NVDA",
        fiscal_period="2025Q3",
        earnings_quality_finding=specialist_finding("EarningsQualityAnalyst"),
        cash_flow_risk_finding=specialist_finding("CashFlowRiskAnalyst"),
        management_intent_finding=specialist_finding("ManagementIntentAnalyst"),
        guidance_finding=specialist_finding("GuidanceAnalyst"),
        financial_agent_results=financial_agent_results or [],
        positive_evidence_pool=[positive],
        negative_evidence_pool=[negative],
        synthesis="Evidence is positive, but cash-flow timing remains a counterpoint.",
    )


def complete_finding_coverage() -> dict[str, str]:
    return {
        "earnings_quality": "supporting",
        "cash_flow_risk": "opposing",
        "management_intent": "supporting",
        "guidance": "not_material",
    }


def completed_status(step: WorkflowStep) -> StepStatus:
    return StepStatus(step=step, state=StepState.COMPLETED)


def test_financial_metrics_normalizes_ticker_and_currency():
    metrics = FinancialMetrics(ticker=" nvda ", fiscal_period="2025Q3", currency=" usd ")

    assert metrics.ticker == "NVDA"
    assert metrics.currency == "USD"


def test_financial_metrics_accepts_canonical_metric_store_entries():
    entry = MetricStoreEntry(
        metric_name="eps_consensus",
        value=0.75,
        unit="USD/share",
        source_type=SourceType.FINANCIAL_API,
        source_name="Yahoo Finance via yfinance",
        fiscal_period="2025Q3",
        period_role="consensus_for_reported_period",
        source_ref=SourceRef(
            source_id="yfinance:NVDA:2025Q3:eps_consensus",
            source_type=SourceType.FINANCIAL_API,
            metric_name="eps_consensus",
            title="Yahoo Finance via yfinance",
            fiscal_period="2025Q3",
            period_role="consensus_for_reported_period",
        ),
    )
    metrics = FinancialMetrics(
        ticker="nvda",
        fiscal_period="2025Q3",
        metric_store=[entry],
    )

    assert metrics.metric_store[0].period_role == "consensus_for_reported_period"
    assert metrics.metric_store[0].source_ref.period_role == "consensus_for_reported_period"


def test_financial_metrics_accepts_presentation_metric_hints_outside_metric_store():
    hint = PresentationMetricHint(
        metric_name="revenue_guidance",
        raw_text="Revenue ($ in millions): 12,000",
        raw_value="12,000",
        value=12_000.0,
        unit="USD million",
        fiscal_period="2025Q4",
        period_role="guided_period",
        source_type=SourceType.EARNINGS_PRESENTATION,
        source_name="FY2025 Q3 earnings presentation",
        source_ref=SourceRef(
            source_id="deck:p4:section-1",
            source_type=SourceType.EARNINGS_PRESENTATION,
            document_id="deck",
            section_id="deck:p4:section-1",
            page=4,
            metric_name="revenue_guidance",
            fiscal_period="2025Q4",
            period_role="guided_period",
        ),
        extraction_method="guidance_hint_regex",
        hint_status="parsed",
        confidence=0.75,
    )

    metrics = FinancialMetrics(
        ticker="nvda",
        fiscal_period="2025Q3",
        presentation_metric_hints=[hint],
    )

    assert metrics.metric_store == []
    assert metrics.presentation_metric_hints[0].hint_status == "parsed"


def test_presentation_metric_hint_rejects_accepted_status():
    with pytest.raises(ValidationError, match="hint_status"):
        PresentationMetricHint(
            metric_name="revenue_guidance",
            raw_text="Revenue: 12,000",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            source_ref=SourceRef(
                source_id="deck:p4:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                section_id="deck:p4:section-1",
            ),
            extraction_method="guidance_hint_regex",
            hint_status="accepted",
        )


def test_presentation_metric_hint_rejects_legacy_period_role():
    with pytest.raises(ValidationError, match="period_role"):
        PresentationMetricHint(
            metric_name="revenue_guidance",
            raw_text="Revenue: 12,000",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            source_ref=SourceRef(
                source_id="deck:p4:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                section_id="deck:p4:section-1",
                metric_name="revenue_guidance",
            ),
            extraction_method="guidance_hint_regex",
            hint_status="parsed",
            period_role="pre_earnings_consensus",
        )


def test_presentation_metric_hint_rejects_legacy_source_ref_period_role():
    with pytest.raises(ValidationError, match="source_ref.period_role"):
        PresentationMetricHint(
            metric_name="revenue_guidance",
            raw_text="Revenue: 12,000",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            source_ref=SourceRef(
                source_id="deck:p4:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                section_id="deck:p4:section-1",
                metric_name="revenue_guidance",
                period_role="pre_earnings_consensus",
            ),
            extraction_method="guidance_hint_regex",
            hint_status="parsed",
        )


def test_presentation_metric_hint_rejects_one_sided_source_ref_period_metadata():
    with pytest.raises(ValidationError, match="source_ref.fiscal_period"):
        PresentationMetricHint(
            metric_name="revenue_guidance",
            raw_text="Revenue: 12,000",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            source_ref=SourceRef(
                source_id="deck:p4:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                section_id="deck:p4:section-1",
                metric_name="revenue_guidance",
                fiscal_period="2025Q4",
            ),
            extraction_method="guidance_hint_regex",
            hint_status="parsed",
        )

    with pytest.raises(ValidationError, match="source_ref.period_role"):
        PresentationMetricHint(
            metric_name="revenue_guidance",
            raw_text="Revenue: 12,000",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            source_ref=SourceRef(
                source_id="deck:p4:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                section_id="deck:p4:section-1",
                metric_name="revenue_guidance",
                period_role="guided_period",
            ),
            extraction_method="guidance_hint_regex",
            hint_status="parsed",
        )


def test_financial_metrics_rejects_legacy_metric_store_period_role():
    with pytest.raises(ValidationError, match="period_role"):
        MetricStoreEntry(
            metric_name="eps_consensus",
            value=0.75,
            unit="USD/share",
            source_type=SourceType.FINANCIAL_API,
            source_name="Yahoo Finance via yfinance",
            fiscal_period="2025Q3",
            period_role="pre_earnings_consensus",
            source_ref=SourceRef(
                source_id="yfinance:NVDA:2025Q3:eps_consensus",
                source_type=SourceType.FINANCIAL_API,
                metric_name="eps_consensus",
            ),
        )


def test_metric_store_entry_requires_aligned_source_ref_metadata():
    with pytest.raises(ValidationError, match="source_ref.metric_name is required"):
        MetricStoreEntry(
            metric_name="revenue_guidance",
            value=28.0,
            unit="USD billion",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            fiscal_period="2025Q4",
            period_role="guided_period",
            source_ref=SourceRef(
                source_id="deck:p4",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="deck",
                fiscal_period="2025Q4",
                period_role="guided_period",
            ),
        )

    with pytest.raises(ValidationError, match="source_ref.source_type"):
        MetricStoreEntry(
            metric_name="revenue_guidance",
            value=28.0,
            unit="USD billion",
            source_type=SourceType.EARNINGS_PRESENTATION,
            source_name="Deck",
            fiscal_period="2025Q4",
            period_role="guided_period",
            source_ref=SourceRef(
                source_id="filing:guidance",
                source_type=SourceType.FILING,
                document_id="10q",
                metric_name="revenue_guidance",
                fiscal_period="2025Q4",
                period_role="guided_period",
            ),
        )


def test_review_request_rejects_legacy_financial_source_ref_period_role():
    with pytest.raises(ValidationError, match="legacy temporal period_role"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                source_refs=[
                    SourceRef(
                        source_id="api:eps-consensus",
                        source_type=SourceType.FINANCIAL_API,
                        metric_name="eps_consensus",
                        fiscal_period="2025Q3",
                        period_role="pre_earnings_consensus",
                    )
                ],
            ),
        )


def test_review_request_rejects_fake_prior_year_metric_store_period():
    entry = MetricStoreEntry(
        metric_name="revenue",
        value=30_000.0,
        unit="USD",
        source_type=SourceType.FINANCIAL_API,
        source_name="Yahoo Finance via yfinance",
        fiscal_period="2025Q2",
        period_role="prior_year_period",
        source_ref=SourceRef(
            source_id="yfinance:NVDA:2025Q2:revenue",
            source_type=SourceType.FINANCIAL_API,
            metric_name="revenue",
            title="Yahoo Finance via yfinance",
            fiscal_period="2025Q2",
            period_role="prior_year_period",
        ),
    )

    with pytest.raises(ValidationError, match="same quarter in the prior fiscal year"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                metric_store=[entry],
            ),
        )


def test_review_request_accepts_prior_sequential_metric_store_period():
    entry = MetricStoreEntry(
        metric_name="revenue",
        value=30_000.0,
        unit="USD",
        source_type=SourceType.FINANCIAL_API,
        source_name="Yahoo Finance via yfinance",
        fiscal_period="2025Q2",
        period_role="prior_sequential_period_actuals",
        source_ref=SourceRef(
            source_id="yfinance:NVDA:2025Q2:revenue",
            source_type=SourceType.FINANCIAL_API,
            metric_name="revenue",
            title="Yahoo Finance via yfinance",
            fiscal_period="2025Q2",
            period_role="prior_sequential_period_actuals",
        ),
    )

    request = ReviewRequest(
        ticker="NVDA",
        fiscal_period="2025Q3",
        prior_fiscal_period="2025Q2",
        financial_metrics=FinancialMetrics(
            ticker="NVDA",
            fiscal_period="2025Q3",
            metric_store=[entry],
        ),
    )

    assert request.prior_fiscal_period == "2025Q2"


def test_review_request_rejects_non_sequential_prior_period_contract():
    entry = MetricStoreEntry(
        metric_name="revenue",
        value=30_000.0,
        unit="USD",
        source_type=SourceType.FINANCIAL_API,
        source_name="Yahoo Finance via yfinance",
        fiscal_period="2024Q3",
        period_role="prior_sequential_period_actuals",
        source_ref=SourceRef(
            source_id="yfinance:NVDA:2024Q3:revenue",
            source_type=SourceType.FINANCIAL_API,
            metric_name="revenue",
            title="Yahoo Finance via yfinance",
            fiscal_period="2024Q3",
            period_role="prior_sequential_period_actuals",
        ),
    )

    with pytest.raises(ValidationError, match="immediately preceding fiscal quarter"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                metric_store=[entry],
            ),
        )


def test_review_request_rejects_conflicting_prior_fiscal_period():
    with pytest.raises(ValidationError, match="prior_fiscal_period"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q1",
            prior_fiscal_period="2024Q3",
            financial_metrics=FinancialMetrics(ticker="NVDA", fiscal_period="2025Q1"),
        )


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


def test_review_request_requires_target_earnings_date_for_automatic_metrics():
    with pytest.raises(ValidationError, match="target_earnings_date is required"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            document_sections=[
                {
                    "section_id": "deck:p1",
                    "source_ref": {
                        "source_id": "deck:p1",
                        "source_type": "earnings_presentation",
                        "document_id": "deck",
                        "section_id": "deck:p1",
                    },
                    "heading": "Deck",
                    "text": "Revenue improved.",
                }
            ],
        )


def test_review_request_rejects_non_target_document_file_period():
    with pytest.raises(ValidationError, match="document_files fiscal_period"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            target_earnings_date="2025-11-19",
            document_files=[
                {
                    "path": "tests/fixtures/sample_presentation.txt",
                    "source_type": "earnings_presentation",
                    "document_id": "deck",
                    "title": "Deck",
                    "fiscal_period": "2025Q2",
                    "period_role": "target_period_document",
                }
            ],
        )


def test_review_request_requires_document_file_period_metadata_with_target_date():
    with pytest.raises(ValidationError, match="document_files fiscal_period is required"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            target_earnings_date="2025-11-19",
            document_files=[
                {
                    "path": "tests/fixtures/sample_presentation.txt",
                    "source_type": "earnings_presentation",
                    "document_id": "deck",
                    "title": "Deck",
                }
            ],
        )


def test_review_request_rejects_flat_metrics_with_latest_snapshot_role():
    with pytest.raises(ValidationError, match="financial_metrics.period_role"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                period_role="latest_snapshot",
            ),
        )


def test_review_request_rejects_latest_snapshot_financial_source_ref():
    with pytest.raises(ValidationError, match="source_refs cannot be latest_snapshot"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                source_refs=[
                    SourceRef(
                        source_id="api:latest",
                        source_type=SourceType.FINANCIAL_API,
                        metric_name="latest_snapshot",
                        period_role="latest_snapshot",
                    )
                ],
            ),
        )


def test_review_request_rejects_latest_snapshot_temporal_snapshot():
    with pytest.raises(ValidationError, match="temporal_snapshots cannot include latest_snapshot"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                temporal_snapshots={
                    "latest_snapshot": {
                        "bucket": "latest_snapshot",
                        "metrics": {"eps_consensus": 1.0},
                    }
                },
            ),
        )


def test_review_request_rejects_financial_data_cutoff_before_target_earnings():
    with pytest.raises(ValidationError, match="financial_data_as_of cannot be before"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            target_earnings_date="2025-11-19",
            financial_data_as_of="2025-11-18",
            financial_metrics=FinancialMetrics(ticker="NVDA", fiscal_period="2025Q3"),
        )


def test_review_request_rejects_future_dated_supplied_metrics():
    with pytest.raises(ValidationError, match="source_row_date must match"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            target_earnings_date="2025-11-19",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                source_row_date="2026-02-18",
            ),
        )


def test_review_request_requires_target_date_for_provider_dated_supplied_metrics():
    with pytest.raises(ValidationError, match="target_earnings_date is required"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                source_row_date="2025-11-19",
            ),
        )


def test_review_request_rejects_wrong_provider_table_column_date():
    with pytest.raises(ValidationError, match="source_table_column_date"):
        ReviewRequest(
            ticker="NVDA",
            fiscal_period="2025Q3",
            target_period_end_date="2025-10-31",
            financial_metrics=FinancialMetrics(
                ticker="NVDA",
                fiscal_period="2025Q3",
                source_table_column_date="2026-01-31",
            ),
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
        "eps_outlook_reason": "Margin strength supports EPS improvement.",
        "fcf_outlook": "FCF may improve after investment intensity normalizes.",
        "fcf_outlook_reason": "FCF depends on investment intensity normalizing.",
    }

    with pytest.raises(ValidationError):
        JudgeDecision(**decision_args)

    decision_args["verdict"] = "good"
    decision = JudgeDecision(**decision_args)

    assert decision.verdict == VerdictLabel.GOOD
    assert VerdictLabel.INSUFFICIENT_EVIDENCE.value == "insufficient_evidence"


def test_agent_role_centers_on_7_agent_contract_with_legacy_name_aliases():
    assert [role.value for role in AgentRole] == [
        "earnings_quality",
        "cash_flow_risk",
        "management_intent",
        "guidance",
        "bull",
        "bear",
        "judge",
    ]
    assert AgentRole.EPS_ANALYST is AgentRole.EARNINGS_QUALITY
    assert AgentRole.PNL_ANALYST is AgentRole.EARNINGS_QUALITY
    assert AgentRole.CFS_ANALYST is AgentRole.CASH_FLOW_RISK
    assert AgentRole.BS_ANALYST is AgentRole.CASH_FLOW_RISK
    assert AgentRole.MANAGEMENT_EVAL is AgentRole.MANAGEMENT_INTENT

    result = AgentResult(
        agent_role="eps_analyst",
        team=AgentTeam.FINANCIAL,
        status=completed_status(WorkflowStep.FINANCIAL_AGENTS),
        headline="Legacy role strings are normalized.",
        conclusion="The canonical role is earnings_quality.",
        confidence=0.7,
    )
    assert result.agent_role is AgentRole.EARNINGS_QUALITY


def test_analysis_brief_requires_four_specialist_findings():
    brief = analysis_brief()

    assert brief.earnings_quality_finding.agent_name == "EarningsQualityAnalyst"
    assert brief.cash_flow_risk_finding.agent_name == "CashFlowRiskAnalyst"
    assert brief.management_intent_finding.agent_name == "ManagementIntentAnalyst"
    assert brief.guidance_finding.agent_name == "GuidanceAnalyst"

    with pytest.raises(ValidationError):
        AnalysisBrief(
            ticker="NVDA",
            fiscal_period="2025Q3",
            earnings_quality_finding=specialist_finding("EarningsQualityAnalyst"),
            cash_flow_risk_finding=specialist_finding("CashFlowRiskAnalyst"),
            management_intent_finding=specialist_finding("ManagementIntentAnalyst"),
            positive_evidence_pool=[evidence()],
            negative_evidence_pool=[evidence("ev:negative:fcf", EvidencePolarity.NEGATIVE)],
            synthesis="Missing guidance finding should fail.",
        )


def test_bull_and_bear_cases_require_complete_finding_coverage():
    positive = evidence()
    negative = evidence("ev:negative:capex", EvidencePolarity.NEGATIVE)
    bull = BullCase(
        thesis="EPS quality and guidance support a constructive view.",
        stance_strength="moderate",
        strongest_positive_evidence=[positive],
        eps_bull_argument="EPS can improve if margin strength persists.",
        fcf_bull_argument="FCF can improve if CapEx intensity moderates.",
        conditions_needed=["Demand remains durable."],
        weak_points=["Near-term FCF remains pressured."],
        finding_coverage=complete_finding_coverage(),
        confidence=0.7,
    )
    bear = BearCase(
        thesis="Cash-flow pressure and execution risk limit the verdict.",
        stance_strength="moderate",
        strongest_negative_evidence=[negative],
        eps_bear_argument="EPS may rely on margin assumptions that could fade.",
        fcf_bear_argument="FCF may stay pressured if CapEx remains high.",
        failure_modes=["CapEx remains elevated."],
        counter_to_bull_case=["Bull case depends on sustained demand."],
        finding_coverage=complete_finding_coverage(),
        confidence=0.65,
    )

    assert bull.finding_coverage["earnings_quality"] == FindingCoverage.SUPPORTING
    assert bear.finding_coverage["cash_flow_risk"] == FindingCoverage.OPPOSING

    incomplete_coverage = complete_finding_coverage()
    incomplete_coverage.pop("guidance")
    with pytest.raises(ValidationError):
        BullCase(
            thesis="Coverage is incomplete.",
            stance_strength="weak",
            strongest_positive_evidence=[positive],
            eps_bull_argument="EPS argument.",
            fcf_bull_argument="FCF argument.",
            conditions_needed=["Condition."],
            weak_points=["Weak point."],
            finding_coverage=incomplete_coverage,
            confidence=0.4,
        )


def test_final_verdict_alias_preserves_judge_decision_api():
    assert FinalVerdict is JudgeDecision

    verdict = FinalVerdict(
        verdict="neutral",
        confidence=0.6,
        summary="Mixed quarter.",
        rationale="Positive evidence and cash-flow risk are balanced.",
        positive_evidence=[evidence()],
        negative_evidence=[evidence("ev:negative:fcf", EvidencePolarity.NEGATIVE)],
        eps_outlook="EPS path is balanced.",
        eps_outlook_reason="EPS positives and risks are balanced.",
        fcf_outlook="FCF path is uncertain.",
        fcf_outlook_reason="FCF conversion remains uncertain.",
    )

    assert isinstance(verdict, JudgeDecision)


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
            eps_outlook_reason="EPS positives and risks are balanced.",
            fcf_outlook="FCF path is uncertain.",
            fcf_outlook_reason="FCF conversion remains uncertain.",
        )


def test_full_review_response_contains_structured_result_and_markdown():
    positive = evidence()
    negative = evidence("ev:negative:capex", EvidencePolarity.NEGATIVE)
    status = completed_status(WorkflowStep.JUDGE)
    agent_result = AgentResult(
        agent_role=AgentRole.EARNINGS_QUALITY,
        team=AgentTeam.FINANCIAL,
        status=status,
        headline="EPS beat was operating-supported.",
        conclusion="Margin expansion supported the EPS beat.",
        key_evidence=[positive],
        counter_evidence=[negative],
        confidence=0.75,
    )
    brief = analysis_brief(
        positive=positive,
        negative=negative,
        financial_agent_results=[agent_result],
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
        eps_outlook_reason="Margin expansion supports EPS upside.",
        fcf_outlook="FCF can improve if CapEx intensity moderates.",
        fcf_outlook_reason="FCF depends on CapEx intensity moderating.",
    )
    bull = BullCase(
        thesis="EPS quality and guidance support a good interpretation.",
        stance_strength="moderate",
        strongest_positive_evidence=[positive],
        eps_bull_argument="EPS can improve if margin strength persists.",
        fcf_bull_argument="FCF can improve if CapEx intensity moderates.",
        conditions_needed=["Demand remains durable."],
        weak_points=["Near-term FCF remains pressured."],
        finding_coverage=complete_finding_coverage(),
        confidence=0.7,
    )
    bear = BearCase(
        thesis="Higher CapEx pressures near-term FCF.",
        stance_strength="moderate",
        strongest_negative_evidence=[negative],
        eps_bear_argument="EPS may rely on margin assumptions that could fade.",
        fcf_bear_argument="FCF may stay pressured if CapEx remains high.",
        failure_modes=["CapEx remains elevated."],
        counter_to_bull_case=["Bull case depends on sustained demand."],
        finding_coverage=complete_finding_coverage(),
        confidence=0.65,
    )

    response = ReviewResponse(
        request_id="req-1",
        ticker="nvda",
        fiscal_period="2025Q3",
        steps=[status],
        analysis_brief=brief,
        bull_case=bull,
        bear_case=bear,
        debate_result=debate,
        judge_decision=decision,
        markdown_report="# Earnings Review\n\nVerdict: good",
    )

    assert response.ticker == "NVDA"
    assert response.markdown_report.startswith("# Earnings Review")
    assert response.is_investment_advice is False


def test_review_response_allows_real_llm_length_markdown_report():
    evidence_positive = evidence("ev:positive", EvidencePolarity.POSITIVE)
    evidence_negative = evidence("ev:negative", EvidencePolarity.NEGATIVE)
    brief = analysis_brief(evidence_positive, evidence_negative)
    brief = AnalysisBrief(
        ticker="NVDA",
        fiscal_period="2025Q3",
        earnings_quality_finding=brief.earnings_quality_finding,
        cash_flow_risk_finding=brief.cash_flow_risk_finding,
        management_intent_finding=brief.management_intent_finding,
        guidance_finding=brief.guidance_finding,
        positive_evidence_pool=[evidence_positive],
        negative_evidence_pool=[evidence_negative],
        synthesis="Validated brief.",
    )
    status = StepStatus(step=WorkflowStep.DATA_INGESTION, state=StepState.COMPLETED)

    response = ReviewResponse(
        ticker="NVDA",
        fiscal_period="2025Q3",
        steps=[status],
        analysis_brief=brief,
        bull_case=BullCase(
            thesis="Positive case.",
            stance_strength="moderate",
            strongest_positive_evidence=[evidence_positive],
            eps_bull_argument="EPS case.",
            fcf_bull_argument="FCF case.",
            conditions_needed=["Execution remains on track."],
            weak_points=["FCF risk remains."],
            finding_coverage=complete_finding_coverage(),
            confidence=0.7,
        ),
        bear_case=BearCase(
            thesis="Negative case.",
            stance_strength="moderate",
            strongest_negative_evidence=[evidence_negative],
            eps_bear_argument="EPS risk.",
            fcf_bear_argument="FCF risk.",
            failure_modes=["CapEx remains high."],
            counter_to_bull_case=["FCF risk remains."],
            finding_coverage=complete_finding_coverage(),
            confidence=0.6,
        ),
        debate_result=DebateResult(
            bull_case="Bull case.",
            bear_case="Bear case.",
            risk_case="Risk case.",
            evaluation="Balanced.",
            strongest_positive_evidence=[evidence_positive],
            strongest_negative_evidence=[evidence_negative],
        ),
        judge_decision=JudgeDecision(
            verdict=VerdictLabel.GOOD,
            confidence=0.65,
            summary="Summary.",
            rationale="Rationale.",
            positive_evidence=[evidence_positive],
            negative_evidence=[evidence_negative],
            eps_outlook="EPS outlook.",
            eps_outlook_reason="EPS reason.",
            fcf_outlook="FCF outlook.",
            fcf_outlook_reason="FCF reason.",
        ),
        markdown_report="# Earnings Review\n\n" + ("Detailed analysis.\n" * 1600),
    )

    assert len(response.markdown_report) > 20000
