from __future__ import annotations

from threading import Lock

from fastapi.testclient import TestClient

from src import api
from src.llm import LLMResponse
from src.workflow import ReviewWorkflow
from src.workflow_models import ReviewRequest


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
            "EPSQualityAnalyst",
            "ProfitabilityAnalyst",
            "CashFlowFcfAnalyst",
            "BalanceSheetRiskAnalyst",
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
              "evidence_id": "EPSQualityAnalyst:positive",
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
              "evidence_id": "CashFlowFcfAnalyst:negative",
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
              "evidence_id": "EPSQualityAnalyst:positive",
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
              "evidence_id": "CashFlowFcfAnalyst:negative",
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
          "fcf_outlook": "FCF can improve after investment intensity moderates."
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
    assert [result.agent_role.value for result in response.analysis_brief.financial_agent_results] == [
        "eps_analyst",
        "pnl_analyst",
        "cfs_analyst",
        "bs_analyst",
    ]
    assert fake_llm.calls.count("judge") == 1


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
