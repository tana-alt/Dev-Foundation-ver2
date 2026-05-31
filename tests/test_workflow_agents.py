import pytest

from src.llm import LLMResponse
from src.workflow_agents import (
    ALL_WORKFLOW_AGENT_CLASSES,
    SPECIALIST_AGENT_CLASSES,
    AgentOutputValidationError,
    BearAgent,
    BullAgent,
    CashFlowRiskAnalyst,
    EarningsQualityAnalyst,
    GuidanceAnalyst,
    JudgeAgent,
    JudgeDecision,
    build_default_agents,
)


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


def earnings_quality_json(agent_name="EarningsQualityAnalyst"):
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


def cash_flow_risk_json(agent_name="CashFlowRiskAnalyst"):
    return f"""
    {{
      "agent_name": "{agent_name}",
      "stance": "mixed",
      "summary": "FCF is pressured by CapEx but liquidity is adequate.",
      "key_evidence": [
        {evidence_json("ev:fcf:positive", "positive", "filing:fcf")}
      ],
      "counter_evidence": [
        {evidence_json("ev:fcf:negative", "negative", "filing:capex")}
      ],
      "confidence": 0.66,
      "missing_data": [],
      "handoff_summary": "FCF outlook is mixed because CapEx remains elevated."
    }}
    """


def guidance_json(source_ref):
    return f"""
    {{
      "agent_name": "GuidanceAnalyst",
      "stance": "mixed",
      "summary": "Guidance is above consensus but execution risk remains.",
      "key_evidence": [
        {{
          "evidence_id": "ev:guidance:positive",
          "polarity": "positive",
          "summary": "Guidance exceeded consensus.",
          "detail": "Precomputed guidance consensus delta supports a positive EPS implication.",
          "impact_areas": ["eps"],
          "source_ref": {source_ref},
          "confidence": 0.70
        }}
      ],
      "counter_evidence": [
        {evidence_json("ev:guidance:negative", "negative", "filing:guidance-risk")}
      ],
      "confidence": 0.64,
      "missing_data": [],
      "handoff_summary": "Guidance is positive with execution risk."
    }}
    """


def finding_coverage_json():
    return """
    {
      "earnings_quality": "supporting",
      "cash_flow_risk": "opposing",
      "management_intent": "not_material",
      "guidance": "missing"
    }
    """


def bull_json(include_coverage=True):
    coverage = f'"finding_coverage": {finding_coverage_json()},' if include_coverage else ""
    return f"""
    {{
      "agent_name": "bull_agent",
      "thesis": "The result can be viewed positively because EPS quality improved.",
      "stance_strength": "moderate",
      "strongest_positive_evidence": [
        {evidence_json("ev:bull:positive", "positive")}
      ],
      {coverage}
      "eps_bull_argument": "Operating margin support improves the EPS case.",
      "fcf_bull_argument": "FCF could improve if growth CapEx normalizes.",
      "conditions_needed": ["CapEx normalization remains visible."],
      "weak_points": ["Current FCF conversion is still mixed."],
      "disputed_points_to_watch": ["CapEx timing"],
      "confidence": 0.64,
      "missing_data": []
    }}
    """


def bear_json(include_coverage=True):
    coverage = f'"finding_coverage": {finding_coverage_json()},' if include_coverage else ""
    return f"""
    {{
      "agent_name": "bear_agent",
      "thesis": "The result could remain neutral because FCF pressure is unresolved.",
      "stance_strength": "moderate",
      "strongest_negative_evidence": [
        {evidence_json("ev:bear:negative", "negative", "filing:capex")}
      ],
      {coverage}
      "eps_bear_argument": "EPS improvement may not fully convert to cash.",
      "fcf_bear_argument": "CapEx and working capital keep FCF risk elevated.",
      "failure_modes": ["CapEx remains elevated longer than expected."],
      "counter_to_bull_case": ["EPS strength does not remove cash conversion risk."],
      "unresolved_risks": ["Demand durability"],
      "confidence": 0.61,
      "missing_data": []
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
      "eps_outlook_reason": "Margins and EPS surprise support future EPS.",
      "fcf_outlook": "CapEx timing is still uncertain.",
      "fcf_outlook_reason": "CapEx timing keeps FCF conversion uncertain."
    }
    """


def test_active_runtime_agent_registry_is_plan_seven_agent_design():
    llm = FakeLLM([])
    agents = build_default_agents(llm)

    assert [cls.spec.public_role for cls in SPECIALIST_AGENT_CLASSES] == [
        "EarningsQualityAnalyst",
        "CashFlowRiskAnalyst",
        "ManagementIntentAnalyst",
        "GuidanceAnalyst",
    ]
    assert [cls.spec.public_role for cls in ALL_WORKFLOW_AGENT_CLASSES] == [
        "EarningsQualityAnalyst",
        "CashFlowRiskAnalyst",
        "ManagementIntentAnalyst",
        "GuidanceAnalyst",
        "BullAgent",
        "BearAgent",
        "JudgeAgent",
    ]
    assert set(agents) == {
        "EarningsQualityAnalyst",
        "CashFlowRiskAnalyst",
        "ManagementIntentAnalyst",
        "GuidanceAnalyst",
        "BullAgent",
        "BearAgent",
        "JudgeAgent",
    }


def test_agent_routes_only_plan_context_keys():
    llm = FakeLLM([earnings_quality_json()])
    agent = EarningsQualityAnalyst(llm)

    result = agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2025Q3"},
            "earnings_quality_metrics": {"eps_surprise_pct": 8.2},
            "earnings_quality_sections": [{"source_ref": "10-Q:eps:1", "text": "EPS text"}],
            "eps_metrics": {"legacy": "must not be routed"},
            "cash_flow_risk_metrics": {"fcf": 123},
            "raw_filing": "must not be routed",
        }
    )

    assert result.agent_name == "EarningsQualityAnalyst"
    prompt = llm.calls[0]["user"]
    assert "earnings_quality_metrics" in prompt
    assert "earnings_quality_sections" in prompt
    assert "eps_metrics" not in prompt
    assert "cash_flow_risk_metrics" not in prompt
    assert "raw_filing" not in prompt


def test_cash_flow_risk_agent_uses_cash_flow_risk_contract():
    llm = FakeLLM([cash_flow_risk_json()])
    agent = CashFlowRiskAnalyst(llm)

    result = agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2025Q3"},
            "cash_flow_risk_metrics": {"free_cash_flow": 123},
            "cash_flow_risk_sections": [{"source_ref": "10-Q:fcf:1", "text": "FCF text"}],
        }
    )

    assert result.agent_name == "CashFlowRiskAnalyst"
    assert "cash_flow_risk_metrics" in llm.calls[0]["user"]


def test_agent_rejects_role_mismatch_without_retry_when_disabled():
    llm = FakeLLM([earnings_quality_json(agent_name="GuidanceAnalyst")])
    agent = EarningsQualityAnalyst(llm, max_retries=0)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"run_spec": {"ticker": "NVDA"}})


def test_agent_retries_once_for_invalid_json():
    llm = FakeLLM(["not json", earnings_quality_json()])
    agent = EarningsQualityAnalyst(llm, max_retries=1)

    result = agent.run({"run_spec": {"ticker": "NVDA"}})

    assert result.agent_name == "EarningsQualityAnalyst"
    assert len(llm.calls) == 2
    assert "previous_output_error" in llm.calls[1]["user"]


def test_agent_repair_prompt_explains_financial_source_ref_metric_name():
    invalid_source_ref = """
    {
      "source_id": "financial:guidance:revenue_delta",
      "source_type": "financial_api"
    }
    """
    valid_source_ref = """
    {
      "source_id": "financial:guidance:revenue_delta",
      "source_type": "financial_api",
      "metric_name": "revenue_guidance_consensus_delta"
    }
    """
    llm = FakeLLM([guidance_json(invalid_source_ref), guidance_json(valid_source_ref)])
    agent = GuidanceAnalyst(llm, max_retries=1)

    result = agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2027Q1"},
            "guidance_consensus_deltas": {"revenue_guidance_consensus_delta": 1.2},
            "source_index": [
                {
                    "source_id": "financial:guidance:revenue_delta",
                    "source_type": "financial_api",
                    "metric_name": "revenue_guidance_consensus_delta",
                }
            ],
        }
    )

    repair_prompt = llm.calls[1]["user"]
    assert result.agent_name == "GuidanceAnalyst"
    assert result.key_evidence[0].source_ref.metric_name == "revenue_guidance_consensus_delta"
    assert "previous_output_error" in repair_prompt
    assert "financial source_ref requires metric_name" in repair_prompt
    assert "metric_name" in repair_prompt
    assert "根拠を補正・捏造" in repair_prompt


def test_agent_prompt_requires_exact_source_index_references():
    llm = FakeLLM([earnings_quality_json()])
    agent = EarningsQualityAnalyst(llm)

    agent.run(
        {
            "run_spec": {"ticker": "NVDA", "fiscal_period": "2027Q1"},
            "eps_consensus_delta": {"eps_surprise_pct": 3.2},
            "source_index": [
                {
                    "source_id": "financial:eps_surprise_pct",
                    "source_type": "financial_api",
                    "metric_name": "eps_surprise_pct",
                }
            ],
        }
    )

    user_prompt = llm.calls[0]["user"]
    assert "routed_context.source_index" in user_prompt
    assert "source_id は source_index に存在する値だけを使う" in user_prompt
    assert "financial_api:NVDA:2027Q1" in user_prompt
    assert (
        "source_id, source_type, url, document_id, section_id, metric_name, page, title"
        in user_prompt
    )


def test_agent_stops_after_single_retry():
    llm = FakeLLM(["not json", "still not json"])
    agent = EarningsQualityAnalyst(llm, max_retries=1)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"run_spec": {"ticker": "NVDA"}})

    assert len(llm.calls) == 2


def test_bull_and_bear_schema_requires_finding_coverage():
    assert "finding_coverage" in BullAgent.spec.output_model.model_json_schema()["properties"]
    assert "finding_coverage" in BearAgent.spec.output_model.model_json_schema()["properties"]

    bull = BullAgent(FakeLLM([bull_json()])).run({"analysis_brief": {"summary": "brief"}})
    bear = BearAgent(FakeLLM([bear_json()])).run({"analysis_brief": {"summary": "brief"}})

    assert bull.finding_coverage["earnings_quality"] == "supporting"
    assert bear.finding_coverage["cash_flow_risk"] == "opposing"


def test_bull_agent_rejects_missing_finding_coverage():
    agent = BullAgent(FakeLLM([bull_json(include_coverage=False)]), max_retries=0)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"analysis_brief": {"summary": "brief"}})


def test_bear_agent_rejects_missing_finding_coverage():
    agent = BearAgent(FakeLLM([bear_json(include_coverage=False)]), max_retries=0)

    with pytest.raises(AgentOutputValidationError):
        agent.run({"analysis_brief": {"summary": "brief"}})


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
