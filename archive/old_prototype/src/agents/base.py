"""Base class for analyst agents.

Each analyst gets:
  - a tight role definition (kept <200 tokens to limit role bleed)
  - the structured EarningsContext (numbers pre-extracted)
  - ONLY the filing sections they need

This is the context-engineering discipline in practice: agents do not
receive the full filing, full conversation history, or each other's
raw output. The orchestrator curates what each one sees.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..llm import LLMProvider
from ..models import AnalystOpinion, EarningsContext, FilingSection
from ..structured import parse_model


class BaseAnalyst(ABC):
    role: str = ""  # set by subclasses
    relevant_sections: tuple[str, ...] = ()  # which sections to read

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    def review(
        self,
        context: EarningsContext,
        sections: list[FilingSection],
        briefing: str | None = None,
    ) -> AnalystOpinion:
        # Filter to only the sections this analyst needs
        relevant = [s for s in sections if s.name in self.relevant_sections]
        section_text = "\n\n".join(
            f"## {s.name.upper()}\n{s.text}" for s in relevant
        ) or "No source sections were selected for this agent."
        briefing_text = briefing or "No additional briefing."

        user_msg = (
            f"# Earnings context (pre-extracted numbers)\n"
            f"```json\n{context.model_dump_json(indent=2)}\n```\n\n"
            f"# Additional briefing from upstream workflow\n{briefing_text}\n\n"
            f"# Relevant filing sections\n{section_text}\n\n"
            f"Provide your review as JSON matching this schema:\n"
            f"{{\n"
            f'  "role": "{self.role}",\n'
            f'  "headline": "one sentence stance",\n'
            f'  "key_points": ["..."],\n'
            f'  "evidence": ["quoted phrases or numbers from filing"],\n'
            f'  "concerns": ["..."]\n'
            f"}}\n"
            f"Return ONLY the JSON, no markdown fences."
        )

        resp = self.llm.complete(
            system=self.system_prompt,
            user=user_msg,
            max_tokens=1500,
            temperature=0.6,
        )

        opinion = parse_model(AnalystOpinion, resp.text)
        if opinion.role != self.role:
            raise ValueError(f"Expected {self.role} opinion, got {opinion.role}")
        return opinion
