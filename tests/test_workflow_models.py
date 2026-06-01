import pytest
from pydantic import ValidationError

from src.workflow_errors import WorkflowErrorCategory
from src.workflow_models import (
    AgentResult,
    AgentRole,
    AgentTeam,
    AnalysisBrief,
    BearCase,
    BullCase,
    CashFlowRiskFinding,
    ClaimRecord,
    ClaimType,
    DebateResult,
    DecisionUse,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FactCheckStatus,
    FinalVerdict,
    FinancialMetrics,
    FindingCoverage,
    GuidanceFinding,
    ImpactArea,
    JudgeDecision,
    JudgeTreatment,
    LineRange,
    ManagementIntentFinding,
    MissingDataItem,
    NormalizedReviewRequest,
    ReportMatrix,
    ReviewDryRunResponse,
    ReviewErrorResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
    SourceManifestEntry,
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
        "eps_outlook_reason": "Margin strength supports EPS improvement.",
        "fcf_outlook": "FCF may improve after investment intensity normalizes.",
        "fcf_outlook_reason": "FCF depends on investment intensity normalizing.",
    }

    with pytest.raises(ValidationError):
        JudgeDecision(**decision_args)

    decision_args["verdict"] = "good"
    decision = JudgeDecision(**decision_args)

    assert decision.verdict == VerdictLabel.GOOD


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


def source_manifest() -> list[SourceManifestEntry]:
    return [
        SourceManifestEntry(
            source_id="api:eps:2025Q3",
            source_type=SourceType.FINANCIAL_API,
            title="Financial API",
            metric_name="eps",
            reported_period="2025Q3",
        ),
        SourceManifestEntry(
            source_id="filing:10q:item2",
            source_type=SourceType.FILING,
            title="Q3 10-Q Item 2",
            document_id="10q-2025q3",
            section_id="item2",
            page=14,
            reported_period="2025Q3",
        ),
    ]


def normalized_request_payload() -> dict[str, object]:
    return {
        "schema_version": "review_input.v1",
        "request_id": "req-normalized-1",
        "ticker": " nvda ",
        "fiscal_period": "2025Q3",
        "financial_metrics": FinancialMetrics(
            ticker="NVDA",
            fiscal_period="2025Q3",
            source_refs=[financial_source("eps")],
        ),
        "document_sections": [
            {
                "section_id": "item2",
                "source_ref": filing_source(),
                "heading": "Management discussion",
                "text": "Management described demand strength and investment needs.",
            }
        ],
        "source_manifest": source_manifest(),
        "context_budget": {
            "max_input_tokens": 6000,
            "max_output_tokens": 2000,
            "max_total_tokens": 10000,
        },
        "include_markdown": True,
        "purpose": "earnings_review_not_investment_advice",
        "is_investment_advice": False,
        "dry_run": True,
    }


def test_normalized_review_request_requires_registered_normalized_input():
    request = NormalizedReviewRequest.model_validate(normalized_request_payload())

    assert request.ticker == "NVDA"
    assert request.dry_run is True
    assert request.context_budget.max_total_tokens == 10000
    assert request.registered_source_ids == {"api:eps:2025Q3", "filing:10q:item2"}


def test_normalized_review_request_rejects_raw_acquisition_fields():
    payload = normalized_request_payload()
    payload["filing_url"] = "https://example.com/10-q"

    with pytest.raises(ValidationError, match="raw acquisition fields"):
        NormalizedReviewRequest.model_validate(payload)


def test_normalized_review_request_rejects_unregistered_section_source():
    payload = normalized_request_payload()
    payload["document_sections"] = [
        {
            "section_id": "item2",
            "source_ref": SourceRef(
                source_id="filing:missing",
                source_type=SourceType.FILING,
                document_id="10q-2025q3",
                section_id="item2",
            ),
            "heading": "Management discussion",
            "text": "This section is not registered in the source manifest.",
        }
    ]

    with pytest.raises(ValidationError, match="unregistered source_id"):
        NormalizedReviewRequest.model_validate(payload)


def test_normalized_review_request_rejects_financial_ref_reusing_filing_source_id():
    payload = normalized_request_payload()
    payload["financial_metrics"] = FinancialMetrics(
        ticker="NVDA",
        fiscal_period="2025Q3",
        source_refs=[
            SourceRef(
                source_id="filing:10q:item2",
                source_type=SourceType.FINANCIAL_API,
                metric_name="eps",
            )
        ],
    )

    with pytest.raises(ValidationError, match="source_manifest mismatch.*source_type"):
        NormalizedReviewRequest.model_validate(payload)


def test_normalized_review_request_rejects_document_locator_mismatch():
    payload = normalized_request_payload()
    payload["document_sections"] = [
        {
            "section_id": "item2",
            "source_ref": SourceRef(
                source_id="filing:10q:item2",
                source_type=SourceType.FILING,
                document_id="different-10q",
                section_id="item2",
            ),
            "heading": "Management discussion",
            "text": "This section conflicts with the source manifest document ID.",
        }
    ]

    with pytest.raises(ValidationError, match="source_manifest mismatch.*document_id"):
        NormalizedReviewRequest.model_validate(payload)


def test_report_matrix_separates_fact_interpretation_and_judge_usage():
    fact = evidence()
    fact.fact_check_status = FactCheckStatus.SUPPORTED
    fact.quote = "Adjusted EPS exceeded consensus."
    fact.reported_period = "2025Q3"

    matrix = ReportMatrix(
        source_manifest=source_manifest(),
        evidence_items=[fact],
        claim_records=[
            ClaimRecord(
                claim_id="claim:eps-quality",
                claim_type=ClaimType.INTERPRETATION,
                agent_role=AgentRole.EARNINGS_QUALITY,
                time_scope="2025Q3",
                claim="EPS quality improved because the beat was supported by margin expansion.",
                evidence_ids=[fact.evidence_id],
                counter_evidence_ids=[],
                interpretation="The fact supports earnings quality, but does not prove durability.",
                implication="The report should distinguish current-quarter support from forward outlook.",
                confidence=0.74,
                limitations=["Durability depends on next-quarter margin evidence."],
            )
        ],
        decision_uses=[
            DecisionUse(
                decision_use_id="decision:eps-quality",
                treatment=JudgeTreatment.SUPPORTING,
                claim_id="claim:eps-quality",
                decisive_evidence_ids=[fact.evidence_id],
                rationale="The claim is supported by a checked EPS fact.",
                verdict_impact=EvidencePolarity.POSITIVE,
                confidence_impact=0.12,
            )
        ],
        missing_data_items=[
            MissingDataItem(
                missing_data_id="missing:fcf-bridge",
                topic="FCF bridge",
                reason="The source set does not explain the cash conversion bridge.",
                materiality="medium",
            )
        ],
    )

    assert matrix.evidence_items[0].fact_check_status is FactCheckStatus.SUPPORTED
    assert matrix.claim_records[0].claim_type is ClaimType.INTERPRETATION
    assert matrix.decision_uses[0].treatment is JudgeTreatment.SUPPORTING


def test_report_matrix_rejects_unregistered_evidence_source():
    fact = evidence()
    fact.source_ref = SourceRef(
        source_id="api:missing",
        source_type=SourceType.FINANCIAL_API,
        metric_name="eps",
    )

    with pytest.raises(ValidationError, match="unregistered source_id"):
        ReportMatrix(source_manifest=source_manifest(), evidence_items=[fact])


def test_report_matrix_rejects_metric_source_mismatch():
    fact = evidence()
    fact.source_ref = SourceRef(
        source_id="api:eps:2025Q3",
        source_type=SourceType.FINANCIAL_API,
        metric_name="revenue",
    )

    with pytest.raises(ValidationError, match="source_manifest mismatch.*metric_name"):
        ReportMatrix(source_manifest=source_manifest(), evidence_items=[fact])


def test_report_matrix_rejects_document_source_mismatch():
    fact = evidence()
    fact.source_ref = SourceRef(
        source_id="filing:10q:item2",
        source_type=SourceType.FILING,
        document_id="10q-2025q3",
        section_id="different-item",
    )

    with pytest.raises(ValidationError, match="source_manifest mismatch.*section_id"):
        ReportMatrix(source_manifest=source_manifest(), evidence_items=[fact])


def test_report_matrix_rejects_document_line_range_mismatch():
    fact = evidence()
    fact.source_ref = SourceRef(
        source_id="filing:10q:item2",
        source_type=SourceType.FILING,
        document_id="10q-2025q3",
        section_id="item2",
        line_range=LineRange(start=20, end=22),
    )
    manifest = source_manifest()
    manifest[1] = manifest[1].model_copy(update={"line_range": LineRange(start=10, end=12)})

    with pytest.raises(ValidationError, match="source_manifest mismatch.*line_range"):
        ReportMatrix(source_manifest=manifest, evidence_items=[fact])


def test_response_envelopes_keep_dry_run_separate_from_final_report():
    dry_run = ReviewDryRunResponse(
        request_id="req-normalized-1",
        ticker="NVDA",
        fiscal_period="2025Q3",
        dry_run_status="passed",
        checks=[
            {
                "name": "normalized_input_contract",
                "status": "passed",
                "message": "Input is normalized and source IDs are registered.",
            }
        ],
    )

    dumped = dry_run.model_dump()

    assert dry_run.status is ReviewStatus.DRY_RUN
    assert "judge_decision" not in dumped
    assert "markdown_report" not in dumped

    with pytest.raises(ValidationError):
        ReviewDryRunResponse(
            request_id="req-normalized-1",
            ticker="NVDA",
            fiscal_period="2025Q3",
            dry_run_status="passed",
            checks=[
                {
                    "name": "normalized_input_contract",
                    "status": "passed",
                    "message": "Input is normalized.",
                }
            ],
            markdown_report="# Not allowed",
        )


def test_dry_run_passed_response_cannot_include_errors():
    with pytest.raises(ValidationError, match="passed dry-run response cannot include errors"):
        ReviewDryRunResponse(
            request_id="req-normalized-1",
            ticker="NVDA",
            fiscal_period="2025Q3",
            dry_run_status="passed",
            checks=[
                {
                    "name": "normalized_input_contract",
                    "status": "passed",
                    "message": "Input is normalized.",
                }
            ],
            errors=[
                {
                    "category": WorkflowErrorCategory.INPUT_CONTRACT,
                    "message": "This error should make the dry-run fail.",
                }
            ],
        )


def test_review_error_response_uses_controlled_error_categories():
    response = ReviewErrorResponse(
        request_id="req-normalized-1",
        ticker="NVDA",
        fiscal_period="2025Q3",
        errors=[
            {
                "category": WorkflowErrorCategory.LLM_OUTPUT_SCHEMA,
                "message": "Agent output did not match the JSON schema.",
                "retryable": True,
            }
        ],
    )

    assert response.status is ReviewStatus.FAILED
    assert response.errors[0].category is WorkflowErrorCategory.LLM_OUTPUT_SCHEMA


def test_workflow_error_category_taxonomy_matches_plan_contract():
    assert [category.value for category in WorkflowErrorCategory] == [
        "input_contract",
        "source_manifest",
        "context_budget",
        "provider",
        "provider_transient",
        "provider_config",
        "llm_output_schema",
        "agent_role",
        "evidence_source",
        "evidence_aggregation",
        "quality_gate",
        "render_response",
        "internal_invariant",
    ]
