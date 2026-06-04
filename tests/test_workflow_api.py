from __future__ import annotations

from threading import Lock

import pytest
from fastapi.testclient import TestClient

from src import api
from src.llm import LLMResponse
from src.workflow import MarkdownRenderer, ReviewWorkflow, WorkflowValidationError
from src.workflow_models import (
    AnalysisBrief,
    CashFlowRiskFinding,
    DebateResult,
    EarningsQualityFinding,
    EvidenceItem,
    EvidencePolarity,
    FinancialMetrics,
    GuidanceFinding,
    ImpactArea,
    JudgeDecision,
    ManagementIntentFinding,
    ReviewRequest,
    SourceRef,
    SourceType,
    VerdictLabel,
)
from src.workflow_validation import WorkflowValidationGate


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._lock = Lock()

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        role = self._role_from_system(system)
        if role == "BullAgent":
            text = self._bull_json()
            call_name = "bull"
        elif role == "BearAgent":
            text = self._bear_json()
            call_name = "bear"
        elif role == "JudgeAgent":
            text = self._judge_json()
            call_name = "judge"
        else:
            text = self._finding_json(role)
            call_name = role

        with self._lock:
            self.calls.append(call_name)
        return LLMResponse(text=text, input_tokens=1, output_tokens=1)

    def _role_from_system(self, system: str) -> str:
        for role in (
            "EarningsQualityAnalyst",
            "CashFlowRiskAnalyst",
            "ManagementIntentAnalyst",
            "GuidanceAnalyst",
            "BullAgent",
            "BearAgent",
            "JudgeAgent",
        ):
            if role in system:
                return role
        raise AssertionError(f"unknown role in system prompt: {system}")

    def _finding_json(self, role: str) -> str:
        return f"""
        {{
          "agent_name": "{role}",
          "stance": "mixed",
          "summary": "{role} summary",
          "key_evidence": [
            {self._evidence_json(f"{role}:positive", "positive", "filing:eps", f"{role} positive evidence")}
          ],
          "counter_evidence": [
            {self._evidence_json(f"{role}:negative", "negative", "filing:risk", f"{role} negative evidence")}
          ],
          "confidence": 0.70,
          "missing_data": [],
          "handoff_summary": "{role} handoff"
        }}
        """

    def _bull_json(self) -> str:
        return """
        {
          "agent_name": "bull_agent",
          "thesis": "EPS quality and guidance support a good interpretation.",
          "stance_strength": "moderate",
          "strongest_positive_evidence": [
            {
              "evidence_id": "EarningsQualityAnalyst:positive",
              "polarity": "positive",
              "summary": "EPS quality improved.",
              "detail": "EPS quality improved.",
              "impact_areas": ["eps"],
              "source_ref": {
                "source_id": "filing:eps",
                "source_type": "filing",
                "document_id": "10q-2025q3",
                "section_id": "eps"
              },
              "confidence": 0.70
            }
          ],
          "eps_bull_argument": "Margins support future EPS.",
          "fcf_bull_argument": "FCF can improve as CapEx normalizes.",
          "conditions_needed": ["Revenue growth continues."],
          "weak_points": ["CapEx remains elevated."],
          "finding_coverage": {
            "earnings_quality": "supporting",
            "cash_flow_risk": "opposing",
            "management_intent": "supporting",
            "guidance": "supporting"
          },
          "disputed_points_to_watch": ["FCF conversion"],
          "confidence": 0.68,
          "missing_data": []
        }
        """

    def _bear_json(self) -> str:
        return """
        {
          "agent_name": "bear_agent",
          "thesis": "FCF and execution risks keep the print from being one-sided.",
          "stance_strength": "moderate",
          "strongest_negative_evidence": [
            {
              "evidence_id": "CashFlowRiskAnalyst:negative",
              "polarity": "negative",
              "summary": "CapEx may pressure FCF.",
              "detail": "CapEx may pressure FCF.",
              "impact_areas": ["fcf"],
              "source_ref": {
                "source_id": "filing:risk",
                "source_type": "filing",
                "document_id": "10q-2025q3",
                "section_id": "risk"
              },
              "confidence": 0.70
            }
          ],
          "eps_bear_argument": "Some margin gains may not persist.",
          "fcf_bear_argument": "Near-term investment can pressure FCF.",
          "failure_modes": ["Demand slows."],
          "counter_to_bull_case": ["FCF conversion is not yet proven."],
          "finding_coverage": {
            "earnings_quality": "opposing",
            "cash_flow_risk": "opposing",
            "management_intent": "not_material",
            "guidance": "opposing"
          },
          "unresolved_risks": ["CapEx timing"],
          "confidence": 0.66,
          "missing_data": []
        }
        """

    def _judge_json(self) -> str:
        return """
        {
          "verdict": "good",
          "confidence": 0.76,
          "summary": "EPS quality and FCF path look constructive with caveats.",
          "rationale": "Positive EPS and margin evidence outweighed near-term FCF risks.",
          "positive_evidence": [
            {
              "evidence_id": "EarningsQualityAnalyst:positive",
              "polarity": "positive",
              "summary": "EPS surprise was positive.",
              "detail": "EPS exceeded consensus with margin support.",
              "impact_areas": ["eps"],
              "source_ref": {
                "source_id": "filing:eps",
                "source_type": "filing",
                "document_id": "10q-2025q3",
                "section_id": "eps"
              },
              "confidence": 0.75
            }
          ],
          "negative_evidence": [
            {
              "evidence_id": "CashFlowRiskAnalyst:negative",
              "polarity": "negative",
              "summary": "CapEx may pressure near-term FCF.",
              "detail": "Elevated investment can delay FCF improvement.",
              "impact_areas": ["fcf"],
              "source_ref": {
                "source_id": "filing:risk",
                "source_type": "filing",
                "document_id": "10q-2025q3",
                "section_id": "risk"
              },
              "confidence": 0.70
            }
          ],
          "eps_outlook": "EPS can improve if revenue growth and margin discipline continue.",
          "eps_outlook_reason": "Revenue growth and margin discipline support EPS improvement.",
          "fcf_outlook": "FCF can improve after investment intensity moderates.",
          "fcf_outlook_reason": "FCF can improve if investment intensity moderates."
        }
        """

    def _evidence_json(self, evidence_id: str, polarity: str, source_id: str, summary: str) -> str:
        section_id = source_id.split(":")[-1]
        return f"""
        {{
          "evidence_id": "{evidence_id}",
          "polarity": "{polarity}",
          "summary": "{summary}",
          "detail": "{summary}",
          "impact_areas": ["overall"],
          "source_ref": {{
            "source_id": "{source_id}",
            "source_type": "filing",
            "document_id": "10q-2025q3",
            "section_id": "{section_id}"
          }},
          "confidence": 0.70
        }}
        """


class HallucinatedBullEvidenceLLM(FakeLLM):
    def _bull_json(self) -> str:
        return (
            super()
            ._bull_json()
            .replace(
                "EarningsQualityAnalyst:positive",
                "invented:positive",
            )
        )


class InvestmentAdviceJudgeLLM(FakeLLM):
    def _judge_json(self) -> str:
        return (
            super()
            ._judge_json()
            .replace(
                "EPS quality and FCF path look constructive with caveats.",
                "You should buy the stock.",
            )
        )


class BlockingMissingDataLLM(FakeLLM):
    def _finding_json(self, role: str) -> str:
        payload = super()._finding_json(role)
        if role == "GuidanceAnalyst":
            return payload.replace(
                '"missing_data": []',
                '"missing_data": ["blocking missing data: source-backed guided-period consensus is unavailable"]',
            )
        return payload


class UngroundedMaterialEvidenceLLM(FakeLLM):
    def _finding_json(self, role: str) -> str:
        positive_summary = "Revenue growth was strong"
        negative_summary = "Margin pressure remains"
        return f"""
        {{
          "agent_name": "{role}",
          "stance": "mixed",
          "summary": "{role} summary",
          "key_evidence": [
            {self._evidence_json(f"{role}:positive", "positive", "filing:eps", positive_summary)}
          ],
          "counter_evidence": [
            {self._evidence_json(f"{role}:negative", "negative", "filing:risk", negative_summary)}
          ],
          "confidence": 0.70,
          "missing_data": [],
          "handoff_summary": "{role} handoff"
        }}
        """


class ChangedJudgeSourceLLM(FakeLLM):
    def _judge_json(self) -> str:
        return (
            super()
            ._judge_json()
            .replace(
                '"section_id": "eps"',
                '"section_id": "invented"',
                1,
            )
        )


def _source_ref(section_id: str) -> dict:
    return {
        "source_id": f"filing:{section_id}",
        "source_type": "filing",
        "document_id": "10q-2025q3",
        "section_id": section_id,
    }


def _request_payload() -> dict:
    return {
        "ticker": "nvda",
        "fiscal_period": "2025Q3",
        "financial_metrics": {
            "ticker": "NVDA",
            "fiscal_period": "2025Q3",
            "eps": 0.81,
            "eps_consensus": 0.75,
            "eps_surprise_pct": 8.0,
            "revenue": 35_000_000_000,
            "revenue_consensus": 33_000_000_000,
            "revenue_surprise_pct": 6.1,
            "free_cash_flow": 12_000_000_000,
            "capex": 1_100_000_000,
        },
        "document_sections": [
            {
                "section_id": "eps",
                "source_ref": _source_ref("eps"),
                "heading": "EPS",
                "text": "Diluted EPS exceeded consensus and margin quality improved.",
            },
            {
                "section_id": "guidance",
                "source_ref": _source_ref("guidance"),
                "heading": "Guidance",
                "text": "Management guidance implies continued revenue growth with elevated investment.",
            },
            {
                "section_id": "risk",
                "source_ref": _source_ref("risk"),
                "heading": "Risk",
                "text": "Forward-looking statements note demand uncertainty and CapEx execution risk.",
            },
        ],
    }


def test_review_workflow_runs_ordered_api_first_steps(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    fake_llm = FakeLLM()
    workflow = ReviewWorkflow(llm=fake_llm)

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert response.ticker == "NVDA"
    assert response.fiscal_period == "2025Q3"
    assert response.judge_decision.verdict.value == "good"
    assert "## Negative Evidence" in response.markdown_report
    assert "## Metric Store" in response.markdown_report
    assert "consensus_for_reported_period" in response.markdown_report
    assert "no URL in source_ref" not in response.markdown_report
    assert [step.step.value for step in response.steps] == [
        "data_ingestion",
        "financial_agents",
        "presentation_agents",
        "evidence_aggregation",
        "debate",
        "judge",
        "markdown_renderer",
    ]
    assert [
        result.agent_role.value for result in response.analysis_brief.financial_agent_results
    ] == [
        "earnings_quality",
        "cash_flow_risk",
    ]
    assert set(fake_llm.calls) == {
        "EarningsQualityAnalyst",
        "CashFlowRiskAnalyst",
        "ManagementIntentAnalyst",
        "GuidanceAnalyst",
        "bull",
        "bear",
        "judge",
    }
    assert fake_llm.calls.count("judge") == 1
    assert len(fake_llm.calls) == 7


def test_workflow_markdown_includes_sec_provider_gap_from_metrics(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["financial_metrics"] = {
        "ticker": "NVDA",
        "fiscal_period": "2025Q3",
        "source_provider": "sec",
        "revenue": 35_000_000_000,
    }
    workflow = ReviewWorkflow(llm=FakeLLM())

    response = workflow.run(ReviewRequest.model_validate(payload))

    assert response.judge_decision.verdict is VerdictLabel.GOOD
    assert response.judge_decision.confidence <= 0.40
    assert "Workflow | provider_expected_missing" in response.markdown_report
    assert "SEC fallback did not provide yfinance-expected fields" in response.markdown_report


def test_workflow_routes_body_guidance_with_generic_heading_to_guidance_analyst(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p4:section-1",
        "source_ref": {
            "source_id": "deck:p4:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p4:section-1",
            "page": 4,
            "title": "Investor presentation",
        },
        "heading": "Investor presentation page 4",
        "text": "Q2 FY2027 outlook: revenue is expected to be approximately $28 billion.",
        "start_page": 4,
        "end_page": 4,
    }
    payload["document_sections"] = [
        section for section in payload["document_sections"] if section["section_id"] != "guidance"
    ]
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(ReviewRequest.model_validate(payload))

    context = workflow._build_agent_context(
        ReviewRequest.model_validate(payload),
        metrics,
        sections,
        guidance_fact,
    )

    guidance_section_ids = [section["section_id"] for section in context["guidance_sections"]]
    guidance_report = next(
        report for report in context["routing_report"] if report["agent_name"] == "GuidanceAnalyst"
    )

    assert guidance_fact.status == "found"
    assert "deck:p4:section-1" in guidance_section_ids
    assert guidance_report["routed_section_ids"] == guidance_section_ids
    assert guidance_report["routing_reason"] == "guidance_fact"


def test_workflow_agent_context_routes_metric_store_and_canonical_temporal_buckets(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["financial_metrics"]["temporal_snapshots"] = {
        "reported_period_actuals": {"metrics": {"eps": 0.81}},
        "pre_earnings_consensus": {
            "metrics": {"eps_consensus": 0.75},
            "note": "pre_earnings_consensus",
            "source_refs": [{"period_role": "pre_earnings_consensus"}],
        },
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(request)
    context = workflow._build_agent_context(request, metrics, sections, guidance_fact)

    assert "temporal_snapshots" not in context["cash_flow_risk_metrics"]
    assert "temporal_snapshots" not in context["guidance_metrics"]
    assert "latest_snapshot" not in context["earnings_quality_metrics"]
    assert "pre_earnings_consensus" not in repr(context["earnings_quality_metrics"])
    buckets = context["earnings_quality_metrics"]["canonical_temporal_buckets"]
    assert buckets["reported_period_actuals"]["metrics"]["eps"] == 0.81
    assert buckets["consensus_for_reported_period"]["metrics"]["eps_consensus"] == 0.75
    assert {
        entry["period_role"] for entry in context["earnings_quality_metrics"]["metric_store"]
    } >= {"reported_period_actuals", "consensus_for_reported_period"}


def test_workflow_agent_context_dedupes_sections_with_routing_tags(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"] = [
        {
            "section_id": "deck:guidance",
            "source_ref": {
                "source_id": "deck:guidance",
                "source_type": "earnings_presentation",
                "document_id": "deck",
                "section_id": "deck:guidance",
                "page": 4,
                "title": "Investor presentation",
            },
            "heading": "Q4 outlook",
            "text": "Q4 outlook: revenue is expected to improve while execution risk remains.",
            "start_page": 4,
            "end_page": 4,
        },
        {
            "section_id": "deck:guidance-risk",
            "source_ref": {
                "source_id": "deck:guidance-risk",
                "source_type": "earnings_presentation",
                "document_id": "deck",
                "section_id": "deck:guidance-risk",
                "page": 4,
                "title": "Investor presentation",
            },
            "heading": "Risk assumptions",
            "text": "Execution risk and demand uncertainty remain relevant to the outlook.",
            "start_page": 4,
            "end_page": 4,
        },
        {
            "section_id": "deck:strategy",
            "source_ref": {
                "source_id": "deck:strategy",
                "source_type": "earnings_presentation",
                "document_id": "deck",
                "section_id": "deck:strategy",
                "page": 5,
                "title": "Investor presentation",
            },
            "heading": "Management commentary",
            "text": "Management described platform investment and go-to-market priorities.",
            "start_page": 5,
            "end_page": 5,
        },
    ]
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(request)
    context = workflow._build_agent_context(request, metrics, sections, guidance_fact)

    assert "management_intent_sections" not in context
    assert "strategy_sections" not in context
    assert "mdna_sections" not in context
    assert "guidance_assumptions_sections" not in context

    management_sections = context["management_sections"]
    management_ids = [section["section_id"] for section in management_sections]
    assert management_ids == ["deck:guidance", "deck:strategy"]
    assert len(management_ids) == len(set(management_ids))

    guidance_section = next(
        section for section in management_sections if section["section_id"] == "deck:guidance"
    )
    strategy_section = next(
        section for section in management_sections if section["section_id"] == "deck:strategy"
    )
    assert set(guidance_section["routing_tags"]) >= {"guidance", "management", "risk"}
    assert guidance_section["merged_section_ids"] == ["deck:guidance", "deck:guidance-risk"]
    assert "Execution risk and demand uncertainty" in guidance_section["text"]
    assert set(strategy_section["routing_tags"]) >= {"other", "strategy", "mdna"}
    assert "Routed for:" in guidance_section["routing_context"]

    guidance_sections = context["guidance_sections"]
    guidance_ids = [section["section_id"] for section in guidance_sections]
    assert guidance_ids == ["deck:guidance"]
    assert "Q4 outlook" in guidance_sections[0]["text"]
    assert "Execution risk and demand uncertainty" in guidance_sections[0]["text"]

    routing_report = {report["agent_name"]: report for report in context["routing_report"]}
    assert routing_report["ManagementIntentAnalyst"]["routed_section_ids"] == management_ids
    assert routing_report["GuidanceAnalyst"]["routed_section_ids"] == guidance_ids
    assert (
        routing_report["GuidanceAnalyst"]["routed_section_contexts"][0]["routing_tags"]
        == guidance_sections[0]["routing_tags"]
    )


@pytest.mark.parametrize(
    ("heading", "text", "expected_raw_text"),
    [
        (
            "FY2025 Q3 earnings presentation",
            "Q4 FY2025 outlook. Revenue ($ in millions): 12,000.",
            "Revenue ($ in millions): 12,000",
        ),
        (
            "Q4 FY2025 outlook",
            "Revenue in millions: 12,000.",
            "Revenue in millions: 12,000",
        ),
        (
            "Q4 FY2025 outlook ($ in millions)",
            "Outlook Revenue 12,000.",
            "Outlook Revenue 12,000",
        ),
        (
            "Q4 FY2025 outlook",
            "($ in millions)\nOutlook Revenue 12,000.",
            "Outlook Revenue 12,000",
        ),
    ],
)
def test_workflow_extracts_guidance_pdf_values_into_presentation_hints(
    monkeypatch,
    heading,
    text,
    expected_raw_text,
):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p4:section-1",
        "source_ref": {
            "source_id": "deck:p4:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p4:section-1",
            "page": 4,
            "title": "FY2025 Q3 earnings presentation",
        },
        "heading": heading,
        "text": text,
        "start_page": 4,
        "end_page": 4,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(request)
    context = workflow._build_agent_context(request, metrics, sections, guidance_fact)

    guidance_hints = [
        hint for hint in metrics.presentation_metric_hints if hint.metric_name == "revenue_guidance"
    ]
    assert guidance_hints
    assert guidance_hints[0].hint_status == "parsed"
    assert guidance_hints[0].period_role == "guided_period"
    assert guidance_hints[0].fiscal_period == "2025Q4"
    assert guidance_hints[0].raw_text == expected_raw_text
    assert guidance_hints[0].raw_value == "12,000"
    assert guidance_hints[0].value == 12_000.0
    assert guidance_hints[0].unit == "USD million"
    assert guidance_hints[0].source_type == SourceType.EARNINGS_PRESENTATION
    assert guidance_hints[0].source_name == "FY2025 Q3 earnings presentation"
    assert not [entry for entry in metrics.metric_store if entry.metric_name == "revenue_guidance"]
    assert context["presentation_metric_hints"][0]["hint_status"] == "parsed"
    assert context["presentation_metric_hints"][0]["raw_value"] == "12,000"
    assert "presentation_metric_hints" not in context["earnings_quality_metrics"]
    assert "presentation_metric_hints" not in context["cash_flow_risk_metrics"]
    assert "presentation_metric_hints" not in context["guidance_metrics"]
    buckets = context["guidance_metrics"]["canonical_temporal_buckets"]
    assert not buckets["guided_period"]


def test_report_separates_metric_store_from_presentation_metric_hints():
    source_ref = SourceRef(
        source_id="deck:p4:section-1",
        source_type=SourceType.EARNINGS_PRESENTATION,
        document_id="deck",
        section_id="deck:p4:section-1",
        page=4,
        metric_name="revenue_guidance",
        fiscal_period="2025Q4",
        period_role="guided_period",
    )
    metrics = FinancialMetrics(
        ticker="NVDA",
        fiscal_period="2025Q3",
        eps=0.81,
        presentation_metric_hints=[
            {
                "metric_name": "revenue_guidance",
                "raw_text": "Revenue ($ in millions): 12,000",
                "raw_value": "12,000",
                "value": 12_000.0,
                "unit": "USD million",
                "fiscal_period": "2025Q4",
                "period_role": "guided_period",
                "source_type": "earnings_presentation",
                "source_name": "FY2025 Q3 earnings presentation",
                "source_ref": source_ref,
                "extraction_method": "guidance_hint_regex",
                "hint_status": "parsed",
                "confidence": 0.75,
            },
            {
                "metric_name": "revenue_guidance",
                "raw_text": "Revenue grew 12%",
                "raw_value": "12%",
                "value": 12.0,
                "unit": "%",
                "fiscal_period": "2025Q4",
                "period_role": "guided_period",
                "source_type": "earnings_presentation",
                "source_name": "FY2025 Q3 earnings presentation",
                "source_ref": source_ref,
                "extraction_method": "guidance_hint_regex",
                "hint_status": "rejected",
                "confidence": 0.1,
            },
        ],
    )
    finding = EarningsQualityFinding(
        stance="mixed",
        summary="summary",
        key_evidence=[
            EvidenceItem(
                evidence_id="ev:positive",
                polarity=EvidencePolarity.POSITIVE,
                summary="EPS was positive.",
                detail="EPS was positive.",
                impact_areas=[ImpactArea.EPS],
                source_ref=_source_ref("eps"),
                confidence=0.7,
            )
        ],
        counter_evidence=[
            EvidenceItem(
                evidence_id="ev:negative",
                polarity=EvidencePolarity.NEGATIVE,
                summary="Risk remains.",
                detail="Risk remains.",
                impact_areas=[ImpactArea.OVERALL],
                source_ref=_source_ref("risk"),
                confidence=0.7,
            )
        ],
        confidence=0.7,
        handoff_summary="handoff",
    )
    brief = AnalysisBrief(
        ticker="NVDA",
        fiscal_period="2025Q3",
        earnings_quality_finding=finding,
        cash_flow_risk_finding=CashFlowRiskFinding.model_validate(
            {**finding.model_dump(), "agent_name": "CashFlowRiskAnalyst"}
        ),
        management_intent_finding=ManagementIntentFinding.model_validate(
            {**finding.model_dump(), "agent_name": "ManagementIntentAnalyst"}
        ),
        guidance_finding=GuidanceFinding.model_validate(
            {**finding.model_dump(), "agent_name": "GuidanceAnalyst"}
        ),
        synthesis="synthesis",
    )
    debate = DebateResult(
        bull_case="bull",
        bear_case="bear",
        risk_case="risk",
        evaluation="evaluation",
        strongest_positive_evidence=finding.key_evidence,
        strongest_negative_evidence=finding.counter_evidence,
    )
    decision = JudgeDecision(
        verdict=VerdictLabel.NEUTRAL,
        confidence=0.6,
        summary="summary",
        rationale="rationale",
        eps_outlook="unclear",
        eps_outlook_reason="unclear",
        fcf_outlook="unclear",
        fcf_outlook_reason="unclear",
        positive_evidence=finding.key_evidence,
        negative_evidence=finding.counter_evidence,
    )
    rendered = MarkdownRenderer().render(
        request=ReviewRequest.model_validate(_request_payload()),
        brief=brief,
        debate=debate,
        decision=decision,
        metrics=metrics,
    )

    assert "## Metric Store" in rendered
    assert "## Presentation Metric Hints" in rendered
    assert "Revenue ($ in millions): 12,000" in rendered
    assert "Revenue grew 12%" not in rendered


def test_workflow_extracts_ambiguous_unitless_guidance_hint(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p4:section-1",
        "source_ref": {
            "source_id": "deck:p4:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p4:section-1",
            "page": 4,
            "title": "FY2025 Q3 earnings presentation",
        },
        "heading": "Q4 FY2025 outlook",
        "text": "Outlook Revenue 12,000.",
        "start_page": 4,
        "end_page": 4,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, _, _ = workflow._ingest(request)

    guidance_hints = [
        hint for hint in metrics.presentation_metric_hints if hint.metric_name == "revenue_guidance"
    ]
    assert guidance_hints
    assert guidance_hints[0].hint_status == "ambiguous"
    assert guidance_hints[0].unit is None
    assert not [entry for entry in metrics.metric_store if entry.metric_name == "revenue_guidance"]


def test_guidance_hint_clears_target_document_period_metadata_when_guided_period_unknown(
    monkeypatch,
):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p4:section-1",
        "source_ref": {
            "source_id": "deck:p4:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p4:section-1",
            "page": 4,
            "title": "FY2025 Q3 earnings presentation",
            "fiscal_period": "2025Q3",
            "period_role": "target_period_document",
        },
        "heading": "Outlook",
        "text": "Revenue in millions: 12,000.",
        "start_page": 4,
        "end_page": 4,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())

    metrics, _, _ = workflow._ingest(request)

    guidance_hints = [
        hint for hint in metrics.presentation_metric_hints if hint.metric_name == "revenue_guidance"
    ]
    assert guidance_hints
    assert guidance_hints[0].hint_status == "parsed"
    assert guidance_hints[0].fiscal_period is None
    assert guidance_hints[0].period_role is None
    assert guidance_hints[0].source_ref.fiscal_period is None
    assert guidance_hints[0].source_ref.period_role is None


def test_workflow_rejects_arr_definition_as_guidance_hint(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p30:section-1",
        "source_ref": {
            "source_id": "deck:p30:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p30:section-1",
            "page": 30,
            "title": "FY2025 Q3 earnings presentation",
        },
        "heading": "Financial outlook definitions",
        "text": "Revenue (ARR) refers to the next 12 months of committed recurring revenue.",
        "start_page": 30,
        "end_page": 30,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(request)
    context = workflow._build_agent_context(request, metrics, sections, guidance_fact)

    guidance_hints = [
        hint for hint in metrics.presentation_metric_hints if hint.metric_name == "revenue_guidance"
    ]
    assert guidance_hints
    assert guidance_hints[0].hint_status == "rejected"
    assert not [hint for hint in context["presentation_metric_hints"] if "ARR" in hint["raw_text"]]


def test_workflow_marks_historical_currency_guidance_hint_ambiguous(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p16:section-1",
        "source_ref": {
            "source_id": "deck:p16:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p16:section-1",
            "page": 16,
            "title": "FY2025 Q3 earnings presentation",
        },
        "heading": "Outlook",
        "text": (
            "Revenue of $850 million in Q3 exceeded prior expectations. "
            "We expect continued customer growth next quarter."
        ),
        "start_page": 16,
        "end_page": 16,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, sections, guidance_fact = workflow._ingest(request)
    context = workflow._build_agent_context(request, metrics, sections, guidance_fact)

    guidance_hints = [
        hint for hint in metrics.presentation_metric_hints if hint.metric_name == "revenue_guidance"
    ]
    assert guidance_hints
    assert guidance_hints[0].hint_status == "ambiguous"
    assert context["presentation_metric_hints"][0]["hint_status"] == "ambiguous"


def test_workflow_does_not_extract_historical_percent_as_guidance_metric(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"][1] = {
        "section_id": "deck:p4:section-1",
        "source_ref": {
            "source_id": "deck:p4:section-1",
            "source_type": "earnings_presentation",
            "document_id": "deck",
            "section_id": "deck:p4:section-1",
            "page": 4,
            "title": "FY2025 Q3 earnings presentation",
        },
        "heading": "FY2025 Q3 earnings presentation",
        "text": "Q4 FY2025 outlook. Revenue grew 12% in the reported quarter.",
        "start_page": 4,
        "end_page": 4,
    }
    request = ReviewRequest.model_validate(payload)
    workflow = ReviewWorkflow(llm=FakeLLM())
    metrics, _, _ = workflow._ingest(request)

    assert not [entry for entry in metrics.metric_store if entry.metric_name == "revenue_guidance"]
    assert [
        hint
        for hint in metrics.presentation_metric_hints
        if hint.metric_name == "revenue_guidance" and hint.hint_status == "rejected"
    ]


def test_workflow_not_found_guidance_skips_guidance_llm(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["financial_metrics"].pop("guidance", None)
    payload["document_sections"] = [
        section for section in payload["document_sections"] if section["section_id"] != "guidance"
    ]
    payload["document_sections"][1]["text"] = "Demand uncertainty and CapEx execution risk remain."
    fake_llm = FakeLLM()
    workflow = ReviewWorkflow(llm=fake_llm)

    response = workflow.run(ReviewRequest.model_validate(payload))

    assert "GuidanceAnalyst" not in fake_llm.calls
    assert response.analysis_brief.guidance_finding.guidance_status == "not_found"
    assert response.analysis_brief.guidance_finding.key_evidence == []
    assert response.analysis_brief.guidance_finding.missing_data


def test_workflow_context_budget_failure_happens_before_llm(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    payload = _request_payload()
    payload["document_sections"] = [
        {
            **payload["document_sections"][0],
            "section_id": f"deck:oversized:{index}",
            "source_ref": {
                **payload["document_sections"][0]["source_ref"],
                "source_id": f"deck:oversized:{index}",
                "section_id": f"deck:oversized:{index}",
            },
            "heading": f"Investor presentation page {index}",
            "text": "FY2027 outlook revenue is expected to improve. " * 180,
        }
        for index in range(20)
    ]
    fake_llm = FakeLLM()
    workflow = ReviewWorkflow(llm=fake_llm)

    with pytest.raises(WorkflowValidationError, match="context budget failed"):
        workflow.run(ReviewRequest.model_validate(payload))

    assert fake_llm.calls == []


def test_workflow_rejects_bull_case_evidence_not_in_analysis_brief(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=HallucinatedBullEvidenceLLM())

    with pytest.raises(WorkflowValidationError, match="not present in validated AnalysisBrief"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_workflow_warns_on_investment_advice_text(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=InvestmentAdviceJudgeLLM())

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert response.warnings
    assert "potential investment-advice language" in response.warnings[0]
    assert "## Warnings" in response.markdown_report


def test_workflow_does_not_cap_structural_guidance_missing_data_when_metrics_are_supplied(
    monkeypatch,
):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=BlockingMissingDataLLM())

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert response.judge_decision.verdict.value == "good"
    assert response.judge_decision.confidence > 0.25
    assert (
        "source-backed guided-period consensus"
        in response.analysis_brief.guidance_finding.missing_data[0]
    )
    assert "source-backed guided-period consensus" not in response.markdown_report


def test_workflow_warns_and_caps_ungrounded_material_judge_evidence(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=UngroundedMaterialEvidenceLLM())

    response = workflow.run(ReviewRequest.model_validate(_request_payload()))

    assert response.warnings
    assert "numeric grounding caveat applied" in "\n".join(response.warnings)
    assert response.judge_decision.confidence <= 0.55
    assert "numeric value was not routed" in response.markdown_report
    assert "## Warnings" in response.markdown_report


def test_workflow_rejects_judge_evidence_source_ref_changes(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=ChangedJudgeSourceLLM())

    with pytest.raises(WorkflowValidationError, match="changed the validated source_ref"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_workflow_rejects_source_ref_page_and_title_changes():
    canonical = EvidenceItem(
        evidence_id="doc-e1",
        polarity=EvidencePolarity.POSITIVE,
        summary="s",
        detail="d",
        impact_areas=[ImpactArea.EPS],
        source_ref=SourceRef(
            source_id="doc:p1:section-1",
            source_type=SourceType.EARNINGS_PRESENTATION,
            document_id="doc",
            section_id="doc:p1:section-1",
            page=1,
            title="Title",
        ),
        confidence=0.7,
    )
    changed_page = canonical.model_copy(
        update={
            "source_ref": SourceRef(
                source_id="doc:p1:section-1",
                source_type=SourceType.EARNINGS_PRESENTATION,
                document_id="doc",
                section_id="doc:p1:section-1",
                page=2,
                title="Different title",
            )
        }
    )

    with pytest.raises(WorkflowValidationError, match="changed the validated source_ref"):
        WorkflowValidationGate().validate_evidence_item_against_canonical(
            changed_page,
            canonical,
            "repro",
        )


def test_workflow_canonicalizes_valid_evidence_source_url():
    validator = WorkflowValidationGate()
    canonical = SourceRef(
        source_id="filing:segments",
        source_type=SourceType.FILING,
        url="https://www.sec.gov/Archives/example/nvda.htm",
        document_id="filing-html",
        section_id="filing:segments",
        title="Filing section: segments",
    )
    emitted = EvidenceItem(
        evidence_id="ev-source",
        polarity=EvidencePolarity.POSITIVE,
        summary="Segment evidence.",
        detail="Segment evidence detail.",
        impact_areas=[ImpactArea.OVERALL],
        source_ref=SourceRef(
            source_id="filing:segments",
            source_type=SourceType.FILING,
            document_id="filing-html",
            section_id="filing:segments",
            title="Filing section: segments",
        ),
        confidence=0.7,
    )

    canonical_sources = {validator.source_signature(canonical): canonical}
    validator.validate_evidence_sources([emitted], set(canonical_sources))
    [updated] = validator.canonicalize_evidence_sources([emitted], canonical_sources)

    assert str(updated.source_ref.url) == "https://www.sec.gov/Archives/example/nvda.htm"


def test_reviews_endpoint_delegates_to_workflow():
    fake_llm = FakeLLM()

    def override_workflow() -> ReviewWorkflow:
        return ReviewWorkflow(llm=fake_llm)

    api.app.dependency_overrides[api.get_workflow] = override_workflow
    try:
        client = TestClient(api.app)
        response = client.post("/reviews", json=_request_payload())
    finally:
        api.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "NVDA"
    assert body["judge_decision"]["verdict"] == "good"
    assert body["steps"][-1]["step"] == "markdown_renderer"
    assert "# Earnings Review: NVDA 2025Q3" in body["markdown_report"]
