"""LLM provider abstraction.

Supports Anthropic and OpenAI via a single interface so the rest of the
codebase is provider-agnostic. The choice is controlled by the
`LLM_PROVIDER` environment variable (twelve-factor: config in env).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse: ...


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        from anthropic import Anthropic

        self.client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResponse(
            text=resp.content[0].text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        self.client = OpenAI()  # picks up OPENAI_API_KEY from env
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )


class FakeProvider(LLMProvider):
    """Deterministic provider for local tests and CI."""

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
        with self._lock:
            self.calls.append(role)
        if role == "BullAgent":
            text = self._bull_json()
        elif role == "BearAgent":
            text = self._bear_json()
        elif role == "JudgeAgent":
            text = self._judge_json()
        else:
            text = self._finding_json(role)
        return LLMResponse(text=text, input_tokens=1, output_tokens=1)

    def _role_from_system(self, system: str) -> str:
        for line in system.splitlines()[:5]:
            if line.startswith("<!-- ROLE: ") and line.endswith(" -->"):
                return line.removeprefix("<!-- ROLE: ").removesuffix(" -->")
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
        raise ValueError("FakeProvider could not infer workflow role")

    def _finding_json(self, role: str) -> str:
        return f"""
        {{
          "agent_name": "{role}",
          "stance": "mixed",
          "summary": "{role} found usable evidence with a counterpoint.",
          "key_evidence": [
            {self._evidence_json(f"{role}:positive", "positive", "filing:eps", f"{role} positive evidence supports EPS or FCF improvement.")}
          ],
          "counter_evidence": [
            {self._evidence_json(f"{role}:negative", "negative", "filing:risk", f"{role} negative evidence keeps the outlook balanced.")}
          ],
          "confidence": 0.70,
          "missing_data": [],
          "handoff_summary": "{role} handoff includes both supporting and opposing evidence."
        }}
        """

    def _bull_json(self) -> str:
        return """
        {
          "agent_name": "bull_agent",
          "thesis": "EPS quality, management execution, and guidance evidence support a good interpretation.",
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
          "eps_bull_argument": "Precomputed EPS and margin evidence support future EPS.",
          "fcf_bull_argument": "FCF can improve if investment intensity moderates.",
          "conditions_needed": ["Revenue growth and margin discipline continue."],
          "weak_points": ["Near-term FCF pressure remains a valid counterpoint."],
          "finding_coverage": {
            "earnings_quality": "supporting",
            "cash_flow_risk": "opposing",
            "management_intent": "supporting",
            "guidance": "supporting"
          },
          "disputed_points_to_watch": ["FCF conversion timing"],
          "confidence": 0.68,
          "missing_data": []
        }
        """

    def _bear_json(self) -> str:
        return """
        {
          "agent_name": "bear_agent",
          "thesis": "FCF pressure and execution risk keep the result from being one-sided.",
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
          "eps_bear_argument": "Some EPS improvement may rely on conditions that need to persist.",
          "fcf_bear_argument": "CapEx and working capital can delay FCF improvement.",
          "failure_modes": ["Demand slows or investment intensity remains elevated."],
          "counter_to_bull_case": ["EPS strength does not by itself prove cash conversion."],
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
          "negative_evidence": [
            {
              "evidence_id": "CashFlowRiskAnalyst:negative",
              "polarity": "negative",
              "summary": "CapEx may pressure near-term FCF.",
              "detail": "CapEx may pressure near-term FCF.",
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


def get_provider() -> LLMProvider:
    """Factory: chooses provider based on LLM_PROVIDER env var."""
    name = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if name == "fake":
        return FakeProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")
