from src.report_renderer import ReportRenderer
from src.workflow_models import (
    AgentRole,
    AnalysisBrief,
    CashFlowRiskFinding,
    ClaimRecord,
    ClaimType,
    DebateResult,
    DecisionUse,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FactCheckStatus,
    GuidanceFinding,
    ImpactArea,
    JudgeDecision,
    JudgeTreatment,
    ManagementIntentFinding,
    MissingDataItem,
    ReportMatrix,
    ReviewRequest,
    SourceManifestEntry,
    SourceRef,
    SourceType,
)


def financial_source() -> SourceRef:
    return SourceRef(
        source_id="api:eps:2025Q3",
        source_type=SourceType.FINANCIAL_API,
        metric_name="eps",
        title="Financial API EPS",
        reported_period="2025Q3",
    )


def filing_source() -> SourceRef:
    return SourceRef(
        source_id="filing:capex:2025Q3",
        source_type=SourceType.FILING,
        document_id="10q-2025q3",
        section_id="capex",
        page=16,
        title="Q3 10-Q CapEx section",
        reported_period="2025Q3",
    )


def positive_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev:eps-beat",
        polarity=EvidencePolarity.POSITIVE,
        summary="Adjusted EPS of $1.23 exceeded consensus by 8%.",
        detail="Adjusted EPS was $1.23 versus consensus of $1.14.",
        impact_areas=[ImpactArea.EPS],
        source_ref=financial_source(),
        metric_name="eps",
        value=1.23,
        unit="USD/share",
        reported_period="2025Q3",
        fact_check_status=FactCheckStatus.SUPPORTED,
        confidence=0.86,
    )


def negative_evidence() -> EvidenceItem:
    return EvidenceItem(
        evidence_id="ev:capex-pressure",
        polarity=EvidencePolarity.NEGATIVE,
        summary="CapEx rose to $3.0B, pressuring free cash flow.",
        detail="The filing shows higher investment intensity during the quarter.",
        impact_areas=[ImpactArea.FCF],
        source_ref=filing_source(),
        metric_name="capex",
        value=3_000_000_000,
        unit="USD",
        reported_period="2025Q3",
        fact_check_status=FactCheckStatus.PARTIALLY_SUPPORTED,
        confidence=0.72,
    )


def finding(cls, key: EvidenceItem, counter: EvidenceItem, *, missing: list[str] | None = None):
    return cls(
        stance="mixed",
        summary=f"{cls.__name__} found support and caveats.",
        key_evidence=[key],
        counter_evidence=[counter],
        confidence=0.74,
        missing_data=missing or [],
        handoff_summary=f"{cls.__name__} handoff uses validated evidence only.",
    )


def renderer_inputs():
    positive = positive_evidence()
    negative = negative_evidence()
    request = ReviewRequest(ticker="NVDA", fiscal_period="2025Q3")
    brief = AnalysisBrief(
        ticker="NVDA",
        fiscal_period="2025Q3",
        earnings_quality_finding=finding(EarningsQualityFinding, positive, negative),
        cash_flow_risk_finding=finding(
            CashFlowRiskFinding,
            positive,
            negative,
            missing=["FCF bridge from operating cash flow to free cash flow is incomplete."],
        ),
        management_intent_finding=finding(ManagementIntentFinding, positive, negative),
        guidance_finding=finding(
            GuidanceFinding,
            positive,
            negative,
            missing=["Forward guidance source was not routed."],
        ),
        positive_evidence_pool=[positive],
        negative_evidence_pool=[negative],
        risk_evidence_pool=[negative],
        synthesis="Validated evidence is constructive, but cash-flow durability remains uncertain.",
    )
    debate = DebateResult(
        bull_case="Bull case: EPS quality improved on a verified beat.",
        bear_case="Bear case: CapEx pressure can delay FCF conversion.",
        risk_case="Risk case: missing guidance limits forward confidence.",
        evaluation="Bull evidence is stronger for the current quarter, while bear evidence limits durability.",
        strongest_positive_evidence=[positive],
        strongest_negative_evidence=[negative],
        unresolved_questions=["How much of CapEx pressure reverses next quarter?"],
    )
    decision = JudgeDecision(
        verdict="neutral",
        confidence=0.66,
        summary="The quarter is constructive, with cash-flow caveats.",
        rationale="The Judge treated the EPS fact as supporting, but discounted durability due to CapEx.",
        positive_evidence=[positive],
        negative_evidence=[negative],
        eps_outlook="EPS outlook is constructive if margin support persists.",
        eps_outlook_reason="The EPS beat is supported by a checked financial source.",
        fcf_outlook="FCF outlook remains uncertain until the CapEx bridge is clearer.",
        fcf_outlook_reason="CapEx pressure and missing bridge data limit confidence.",
    )
    matrix = ReportMatrix(
        source_manifest=[
            SourceManifestEntry(
                source_id="api:eps:2025Q3",
                source_type=SourceType.FINANCIAL_API,
                title="Financial API EPS",
                metric_name="eps",
                reported_period="2025Q3",
            ),
            SourceManifestEntry(
                source_id="filing:capex:2025Q3",
                source_type=SourceType.FILING,
                title="Q3 10-Q CapEx section",
                document_id="10q-2025q3",
                section_id="capex",
                page=16,
                reported_period="2025Q3",
            ),
        ],
        evidence_items=[positive, negative],
        claim_records=[
            ClaimRecord(
                claim_id="claim:eps-quality",
                claim_type=ClaimType.INTERPRETATION,
                agent_role=AgentRole.EARNINGS_QUALITY,
                time_scope="Current quarter 2025Q3",
                claim="EPS quality improved because the beat was supported by reported EPS.",
                evidence_ids=[positive.evidence_id],
                counter_evidence_ids=[negative.evidence_id],
                interpretation="The fact supports current-quarter EPS quality.",
                implication="The report should avoid converting the fact into a durable forecast.",
                confidence=0.76,
                limitations=["Durability depends on margin and CapEx evidence."],
            )
        ],
        decision_uses=[
            DecisionUse(
                decision_use_id="decision:eps-quality",
                treatment=JudgeTreatment.SUPPORTING,
                claim_id="claim:eps-quality",
                decisive_evidence_ids=[positive.evidence_id],
                rationale="The checked EPS fact supports the neutral-to-positive EPS treatment.",
                verdict_impact=EvidencePolarity.POSITIVE,
                confidence_impact=0.10,
            )
        ],
        missing_data_items=[
            MissingDataItem(
                missing_data_id="missing:fcf-bridge",
                topic="FCF bridge",
                reason="The source set does not explain conversion from operating cash flow to FCF.",
                materiality="medium",
            )
        ],
    )
    return request, brief, debate, decision, matrix


def render_report() -> str:
    request, brief, debate, decision, matrix = renderer_inputs()
    return ReportRenderer().render(
        request=request,
        brief=brief,
        debate=debate,
        decision=decision,
        matrix=matrix,
    )


def section(markdown: str, heading: str) -> str:
    start = markdown.index(f"## {heading}")
    next_start = markdown.find("\n## ", start + 1)
    if next_start == -1:
        return markdown[start:]
    return markdown[start:next_start]


def test_renderer_outputs_final_section_order():
    markdown = render_report()
    headings = [
        "Judge Rationale",
        "Bull vs Bear Tension",
        "Evidence Matrix",
        "Agent Contribution",
        "Uncertainty And Missing Data",
        "Quality Gates",
        "Source Appendix",
        "Disclaimer",
    ]

    positions = [markdown.index(f"## {heading}") for heading in headings]

    assert positions == sorted(positions)


def test_evidence_matrix_distinguishes_contract_fields():
    matrix_section = section(render_report(), "Evidence Matrix")

    assert (
        "| Claim ID | Fact | Interpretation | Implication | Time scope | "
        "Fact-check status | Judge treatment | Sources |"
    ) in matrix_section
    assert "Adjusted EPS of $1.23 exceeded consensus by 8%." in matrix_section
    assert "The fact supports current-quarter EPS quality." in matrix_section
    assert "The report should avoid converting the fact into a durable forecast." in matrix_section
    assert "Current quarter 2025Q3" in matrix_section
    assert "supported" in matrix_section
    assert "supporting" in matrix_section


def test_source_appendix_does_not_duplicate_unrelated_sections():
    source_appendix = section(render_report(), "Source Appendix")

    assert source_appendix.count("api:eps:2025Q3") == 1
    assert source_appendix.count("filing:capex:2025Q3") == 1
    assert "Q3 10-Q CapEx section" in source_appendix
    assert "Evidence Matrix" not in source_appendix
    assert "Quality Gates" not in source_appendix
    assert "Bull vs Bear Tension" not in source_appendix


def test_quality_gates_and_disclaimer_are_visible():
    markdown = render_report()
    quality_gates = section(markdown, "Quality Gates")
    disclaimer = section(markdown, "Disclaimer")

    assert "ReportMatrix validation: passed" in quality_gates
    assert "Evidence items: 2" in quality_gates
    assert "supported: 1" in quality_gates
    assert "not investment advice" in disclaimer
