"""Domain models for the earnings debate system.

These pydantic models double as the structured-context contract between
agents — they make it explicit what data flows where, which is the
key idea behind context engineering for agents.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


NonEmptyText = Annotated[str, Field(min_length=1)]


class ContractModel(BaseModel):
    """Strict base for data exchanged between pipeline stages."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class FilingSection(ContractModel):
    """A semantic chunk of an earnings filing."""
    name: Literal["revenue", "eps", "guidance", "segments", "risk", "other"]
    text: str = Field(min_length=1, max_length=8000)


class EarningsContext(ContractModel):
    """Structured numerical context. Injected into agent prompts so the
    LLM never has to *find* these numbers — eliminating a major source
    of hallucination."""
    ticker: str = Field(min_length=1, max_length=15)
    quarter: str = Field(pattern=r"^\d{4}Q[1-4]$")  # e.g. "2025Q3"

    eps_actual: float | None = None
    eps_consensus: float | None = None
    eps_surprise_pct: float | None = None
    eps_yoy: float | None = None

    revenue_actual: float | None = None
    revenue_consensus: float | None = None
    revenue_surprise_pct: float | None = None
    revenue_yoy_pct: float | None = None

    guidance_summary: str | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = str(value).upper().strip()
        if not re.fullmatch(r"[A-Z0-9.\-]{1,15}", normalized):
            raise ValueError("ticker must contain only letters, numbers, dots, or hyphens")
        return normalized


class AnalystOpinion(ContractModel):
    role: Literal[
        "eps_analyst",
        "pnl_analyst",
        "cfs_analyst",
        "bs_analyst",
        "management_eval",
        "guidance",
        "bull",
        "bear",
        "risk",
        # Kept for backward compatibility with the earlier prototype.
        "quants",
        "macro",
    ]
    headline: str = Field(min_length=1, max_length=300)  # one-line stance
    key_points: list[NonEmptyText] = Field(min_length=1, max_length=8)
    evidence: list[NonEmptyText] = Field(min_length=1, max_length=8)  # quoted phrases / numbers from the filing
    concerns: list[NonEmptyText] = Field(default_factory=list, max_length=8)


class DebatePoint(ContractModel):
    """Extracted by the orchestrator from round-1 opinions, then sent
    back into round-2 for cross-examination."""
    topic: str = Field(min_length=1, max_length=300)
    bull_view: str | None = Field(default=None, max_length=600)
    bear_view: str | None = Field(default=None, max_length=600)
    needs_resolution: bool = True


class Verdict(ContractModel):
    label: Literal["GOOD", "NEUTRAL", "BAD"]
    confidence: float = Field(ge=0.0, le=1.0)
    one_liner: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=1200)
    eps_surprise_assessment: str = Field(min_length=1, max_length=800)
    positive_evidence: list[NonEmptyText] = Field(min_length=1, max_length=8)
    negative_evidence: list[NonEmptyText] = Field(min_length=1, max_length=8)
    eps_outlook: str = Field(min_length=1, max_length=800)
    fcf_outlook: str = Field(min_length=1, max_length=800)
