import pytest

from src.llm import LLMResponse
from src.workflow_agents import AgentOutputValidationError, EPSQualityAnalyst
from src.workflow_agents import JudgeAgent, JudgeDecision


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        self.calls.append(
            {
                "system": system,
                "user": user,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        text = self.responses.pop(0)
        return LLMResponse(text=text, input_tokens=1, output_tokens=1)


def evidence_json(evidence_id, polarity, source_id="filing:eps"):
    return f"""
    {{
      "evidence_id": "{evidence_id}",
      "polarity": "{polarity}",
      "summary": "Adjusted EPS exceeded consensus.",
      "detail": "Adjusted EPS exceeded consensus with supporting source text.",
      "impact_areas": ["eps"],
      "source_ref": {{
        "source_id": "{source_id}",
        "source_type": "filing",
        "document_id": "10q-2025q3",
        "section_id": "eps"
      }},
      "confidence": 0.72
    }}
    """


def finding_json(agent_name="EPSQualityAnalyst"):
    return f"""
    {{
      "agent_name": "{agent_name}",
      "stance": "positive",
      "summary": "EPS beat quality looks operating-driven.",
      "key_evidence": [
        {evidence_json("ev:eps:positive", "positive")}
      ],
      "counter_evidence": [
        {evidence_json("ev:eps:negative", "negative", "filing:risk")}
      ],
      "confidence": 0.72,
      "missing_data": [],
      "handoff_summary": "Positive EPS quality with one tax caveat."
    }}
    """


def judge_json():
    return """
    {
      "verdict": "neutral",
      "confidence": 0.61,
      "summary": "Positive EPS evidence is balanced by FCF uncertainty.",
      "rationale": "The print has credible EPS improvement, but FCF conversion remains unresolved.",
      "positive_evidence": [
        {
          "evidence_id": "ev_eps_1",
          "polarity": "positive",
          "summary": "EPS quality improved.",
          "detail": "Adjusted EPS exceeded consensus with operating margin support.",
          "impact_areas": ["eps"],
          "source_ref": {
            "source_id": "derived:eps:1",
            "source_type": "derived_metric",
            "metric_name": "eps_surprise_pct"
          },
          "confidence": 0.72
        }
      ],
      "negative_evidence": [
        {
          "evidence_id": "ev_fcf_1",
          "polarity": "negative",
          "summary": "FCF conversion remains weak.",
          "detail": "CapEx timing makes FCF improvement uncertain.",
          "impact_areas": ["fcf"],
          "source_ref": {
            "source_id": "derived:fcf:1",
            "source_type": "derived_metric",
            "metric_name": "free_cash_flow"
          },
          "confidence": 0.66
        }
      ],
      "eps_outlook": "Margins support future EPS.",
      "fcf_outlook": "CapEx timing is still uncertain."
    }
    """


def test_agent_routes_only_allowed_context_keys():
    llm = FakeLLM([finding_json()])
    agent = EPSQualityAnalyst(llm)

    result = agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2025Q3"},
            "eps_metrics": {"eps_surprise_pct": 8.2},
            "eps_sections": [{"source_ref": "10-Q:eps:1", "text": "EPS text"}],
            "cash_flow_metrics": {"fcf": 123},
            "raw_filing": "must not be routed",
        }
    )

    assert result.agent_name == "EPSQualityAnalyst"
    prompt = llm.calls[0]["user"]
    assert "eps_metrics" in prompt
    assert "eps_sections" in prompt
    assert "cash_flow_metrics" not in prompt
    assert "raw_filing" not in prompt


def test_agent_rejects_role_mismatch_without_retry_when_disabled():
    llm = FakeLLM([finding_json(agent_name="GuidanceAnalyst")])
    agent = EPSQualityAnalyst(llm, max_retries=0)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"run_spec": {"ticker": "NVDA"}})


def test_agent_retries_once_for_invalid_json():
    llm = FakeLLM(["not json", finding_json()])
    agent = EPSQualityAnalyst(llm, max_retries=1)

    result = agent.run({"run_spec": {"ticker": "NVDA"}})

    assert result.agent_name == "EPSQualityAnalyst"
    assert len(llm.calls) == 2
    assert "previous_output_error" in llm.calls[1]["user"]


def test_agent_stops_after_single_retry():
    llm = FakeLLM(["not json", "still not json"])
    agent = EPSQualityAnalyst(llm, max_retries=1)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"run_spec": {"ticker": "NVDA"}})

    assert len(llm.calls) == 2


def test_judge_agent_returns_judge_decision_contract():
    llm = FakeLLM([judge_json()])
    agent = JudgeAgent(llm)

    result = agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2025Q3"},
            "analysis_brief": {"summary": "Validated brief"},
            "bull_case": {"agent_name": "bull_agent"},
            "bear_case": {"agent_name": "bear_agent"},
            "raw_filing": "must not be routed",
        }
    )

    assert isinstance(result, JudgeDecision)
    assert result.verdict.value == "neutral"
    assert "raw_filing" not in llm.calls[0]["user"]
