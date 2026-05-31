"""Report-quality contracts used by additive report-quality modules.

These models intentionally live outside `workflow_models.py` so the existing
workflow contract remains stable. They are helper contracts for renderer/gates
and can be promoted to canonical workflow models later.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from .workflow_models import SourceRef


class SourceTiming(str, Enum):
    SAME_PERIOD_PRIMARY = "same_period_primary"
    CONTEMPORARY_EXTERNAL = "contemporary_external"
    POST_EVENT_EXTERNAL = "post_event_external"
    STALE_EXTERNAL = "stale_external"
    UNKNOWN = "unknown"


class MetricRef(BaseModel):
    metric_id: str
    metric_name: str
    value: float | str | None = None
    unit: str | None = None
    period: str | None = None
    comparator_name: str | None = None
    comparator_value: float | None = None
    delta: float | None = None
    delta_pct: float | None = None
    source_ref: SourceRef


class ClaimEvidence(BaseModel):
    claim_id: str
    claim: str
    direction: Literal["positive", "negative", "neutral", "risk", "mixed", "unclear"]
    evidence_value: str
    interpretation: str
    impact_areas: list[str] = Field(default_factory=list)
    metric_refs: list[MetricRef] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    source_timing: SourceTiming = SourceTiming.UNKNOWN
    agent_name: str
    confidence: float = Field(ge=0.0, le=1.0)


class EvidenceMatrix(BaseModel):
    ticker: str
    fiscal_period: str
    claims: list[ClaimEvidence]


class ExternalSourceCandidate(BaseModel):
    source_id: str
    title: str
    url: str
    publisher: str | None = None
    published_date: date | None = None
    related_event_date: date | None = None
    timing: SourceTiming = SourceTiming.UNKNOWN
    proposed_use: str
    accepted_by_user: bool = False


class ExternalResearchPacket(BaseModel):
    ticker: str
    fiscal_period: str
    candidates: list[ExternalSourceCandidate] = Field(default_factory=list)
