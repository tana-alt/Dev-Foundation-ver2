from __future__ import annotations

from threading import Lock

import pytest
from fastapi.testclient import TestClient

from src import api
from src.llm import LLMResponse
from src.workflow import ReviewWorkflow, WorkflowValidationError
from src.workflow_models import (
    EvidenceItem,
    EvidencePolarity,
    ImpactArea,
    ReviewRequest,
    SourceRef,
    SourceType,
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


def test_workflow_rejects_bull_case_evidence_not_in_analysis_brief(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=HallucinatedBullEvidenceLLM())

    with pytest.raises(WorkflowValidationError, match="not present in validated AnalysisBrief"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


def test_workflow_rejects_investment_advice_text(monkeypatch):
    def fail_external_fetch(*args, **kwargs):
        raise AssertionError("fixture inputs should bypass external fetches")

    monkeypatch.setattr("src.workflow._fetch_consensus", fail_external_fetch)
    monkeypatch.setattr("src.workflow._fetch_filing_html", fail_external_fetch)

    workflow = ReviewWorkflow(llm=InvestmentAdviceJudgeLLM())

    with pytest.raises(WorkflowValidationError, match="investment-advice language"):
        workflow.run(ReviewRequest.model_validate(_request_payload()))


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
