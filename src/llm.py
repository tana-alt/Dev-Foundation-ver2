"""LLM provider abstraction.

Supports Anthropic and OpenAI via a single interface so the rest of the
codebase is provider-agnostic. The choice is controlled by the
`LLM_PROVIDER` environment variable (twelve-factor: config in env).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock
from typing import Any


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
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        params: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if _openai_uses_max_completion_tokens(self.model):
            params["max_completion_tokens"] = max(max_tokens, 4096)
        else:
            params["max_tokens"] = max_tokens
            params["temperature"] = temperature

        resp = self.client.chat.completions.create(**params)
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )


def _openai_uses_max_completion_tokens(model: str) -> bool:
    normalized = model.lower()
    return normalized.startswith(("gpt-5", "o1", "o3", "o4"))


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
        positive_source_ref, negative_source_ref = self._source_refs_from_user(user)
        with self._lock:
            self.calls.append(role)
        if role == "BullAgent":
            text = self._bull_json(positive_source_ref)
        elif role == "BearAgent":
            text = self._bear_json(negative_source_ref)
        elif role == "JudgeAgent":
            text = self._judge_json(positive_source_ref, negative_source_ref)
        else:
            text = self._finding_json(role, positive_source_ref, negative_source_ref)
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

    def _source_refs_from_user(self, user: str) -> tuple[dict[str, Any], dict[str, Any]]:
        fallback_positive = {
            "source_id": "filing:eps",
            "source_type": "filing",
            "document_id": "10q-2025q3",
            "section_id": "eps",
        }
        fallback_negative = {
            "source_id": "filing:risk",
            "source_type": "filing",
            "document_id": "10q-2025q3",
            "section_id": "risk",
        }
        marker = "# routed_context\n"
        schema_marker = "\n\n# expected_output_schema"
        if marker not in user or schema_marker not in user:
            return fallback_positive, fallback_negative
        raw_context = user.split(marker, 1)[1].split(schema_marker, 1)[0]
        try:
            context = json.loads(raw_context)
        except json.JSONDecodeError:
            return fallback_positive, fallback_negative

        brief = (
            context.get("analysis_brief") if isinstance(context.get("analysis_brief"), dict) else {}
        )
        positive_pool = (
            context.get("positive_evidence_pool") or brief.get("positive_evidence_pool") or []
        )
        negative_pool = (
            context.get("negative_evidence_pool")
            or context.get("risk_evidence_pool")
            or brief.get("negative_evidence_pool")
            or brief.get("risk_evidence_pool")
            or []
        )
        if (
            positive_pool
            and isinstance(positive_pool[0], dict)
            and "source_ref" in positive_pool[0]
        ):
            positive = positive_pool[0]["source_ref"]
            negative = (
                negative_pool[0]["source_ref"]
                if negative_pool
                and isinstance(negative_pool[0], dict)
                and "source_ref" in negative_pool[0]
                else positive
            )
            return positive, negative

        source_refs = [
            source_ref
            for source_ref in self._collect_source_refs(context)
            if source_ref.get("source_type") not in {"financial_api", "derived_metric"}
        ]
        if not source_refs:
            return fallback_positive, fallback_negative
        positive = source_refs[0]
        negative = next(
            (
                source_ref
                for source_ref in source_refs
                if "risk" in str(source_ref.get("source_id", "")).lower()
                or "risk" in str(source_ref.get("section_id", "")).lower()
            ),
            source_refs[-1],
        )
        return positive, negative

    def _collect_source_refs(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            source_refs: list[dict[str, Any]] = []
            if "source_id" in value and "source_type" in value:
                source_refs.append(value)
            for child in value.values():
                source_refs.extend(self._collect_source_refs(child))
            return source_refs
        if isinstance(value, list):
            source_refs = []
            for child in value:
                source_refs.extend(self._collect_source_refs(child))
            return source_refs
        return []

    def _finding_json(
        self,
        role: str,
        positive_source_ref: dict[str, Any],
        negative_source_ref: dict[str, Any],
    ) -> str:
        return f"""
        {{
          "agent_name": "{role}",
          "stance": "mixed",
          "summary": "{role} found usable evidence with a counterpoint.",
          "key_evidence": [
            {self._evidence_json(f"{role}:positive", "positive", positive_source_ref, f"{role} positive evidence supports EPS or FCF improvement.")}
          ],
          "counter_evidence": [
            {self._evidence_json(f"{role}:negative", "negative", negative_source_ref, f"{role} negative evidence keeps the outlook balanced.")}
          ],
          "confidence": 0.70,
          "missing_data": [],
          "handoff_summary": "{role} handoff includes both supporting and opposing evidence."
        }}
        """

    def _bull_json(self, source_ref: dict[str, Any]) -> str:
        return json.dumps(
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
                        "source_ref": source_ref,
                        "confidence": 0.70,
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
                    "guidance": "supporting",
                },
                "disputed_points_to_watch": ["FCF conversion timing"],
                "confidence": 0.68,
                "missing_data": [],
            }
        )

    def _bear_json(self, source_ref: dict[str, Any]) -> str:
        return json.dumps(
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
                        "source_ref": source_ref,
                        "confidence": 0.70,
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
                    "guidance": "opposing",
                },
                "unresolved_risks": ["CapEx timing"],
                "confidence": 0.66,
                "missing_data": [],
            }
        )

    def _judge_json(
        self,
        positive_source_ref: dict[str, Any],
        negative_source_ref: dict[str, Any],
    ) -> str:
        return json.dumps(
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
                        "source_ref": positive_source_ref,
                        "confidence": 0.70,
                    }
                ],
                "negative_evidence": [
                    {
                        "evidence_id": "CashFlowRiskAnalyst:negative",
                        "polarity": "negative",
                        "summary": "CapEx may pressure near-term FCF.",
                        "detail": "CapEx may pressure near-term FCF.",
                        "impact_areas": ["fcf"],
                        "source_ref": negative_source_ref,
                        "confidence": 0.70,
                    }
                ],
                "eps_outlook": "EPS can improve if revenue growth and margin discipline continue.",
                "eps_outlook_reason": (
                    "Revenue growth and margin discipline support EPS improvement, "
                    "while counter evidence keeps the assessment conditional."
                ),
                "fcf_outlook": "FCF can improve after investment intensity moderates.",
                "fcf_outlook_reason": (
                    "FCF can improve if investment intensity moderates, but near-term "
                    "CapEx pressure remains a constraint."
                ),
            }
        )

    def _evidence_json(
        self,
        evidence_id: str,
        polarity: str,
        source_ref: dict[str, Any],
        summary: str,
    ) -> str:
        metric_name = "free_cash_flow" if "fcf" in summary.lower() else "eps_surprise_pct"
        unit = "USD" if metric_name == "free_cash_flow" else "%"
        return f"""
        {{
          "evidence_id": "{evidence_id}",
          "polarity": "{polarity}",
          "summary": "{summary}",
          "detail": "{summary}",
          "impact_areas": ["overall"],
          "source_ref": {json.dumps(source_ref)},
          "metric_name": "{metric_name}",
          "value": 1.0,
          "unit": "{unit}",
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
