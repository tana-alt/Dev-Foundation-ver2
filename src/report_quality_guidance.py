"""Guidance acquisition gate.

Guidance is required as a source-backed fact. If the company does not provide
guidance, the absence must itself be source-backed by a routed section.
"""

from __future__ import annotations

import os
import re
from enum import Enum

from pydantic import BaseModel, Field

from .workflow_models import SourceRef


class GuidanceAcquisitionError(ValueError):
    """Raised when guidance is missing or not source-backed."""


class GuidanceStatus(str, Enum):
    FOUND = "found"
    NOT_DISCLOSED = "not_disclosed"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


class GuidanceFact(BaseModel):
    status: GuidanceStatus
    source_refs: list[SourceRef] = Field(default_factory=list)
    reason: str | None = None


GUIDANCE_RE = re.compile(
    r"\b(guidance|outlook|forecast|expects?|expectation|provided\s+guidance|next\s+quarter|full\s+year)\b",
    re.IGNORECASE,
)
NO_GUIDANCE_RE = re.compile(
    r"\b(no\s+guidance|does\s+not\s+provide\s+guidance|not\s+providing\s+guidance|withdrawn\s+guidance|suspended\s+guidance)\b",
    re.IGNORECASE,
)


def extract_guidance_fact(metrics, sections: list) -> GuidanceFact:
    guidance_text = getattr(metrics, "guidance", None)
    metric_refs = list(getattr(metrics, "source_refs", []) or [])
    if isinstance(guidance_text, str) and guidance_text.strip():
        return GuidanceFact(status=GuidanceStatus.FOUND, source_refs=metric_refs)

    guidance_refs: list[SourceRef] = []
    no_guidance_refs: list[SourceRef] = []
    for section in sections:
        heading = getattr(section, "heading", "") or ""
        text = getattr(section, "text", "") or ""
        haystack = f"{heading}\n{text}"
        ref = getattr(section, "source_ref", None)
        if NO_GUIDANCE_RE.search(haystack) and ref is not None:
            no_guidance_refs.append(ref)
        elif GUIDANCE_RE.search(haystack) and ref is not None:
            guidance_refs.append(ref)

    if guidance_refs:
        return GuidanceFact(status=GuidanceStatus.FOUND, source_refs=guidance_refs)
    if no_guidance_refs:
        return GuidanceFact(
            status=GuidanceStatus.NOT_DISCLOSED,
            source_refs=no_guidance_refs,
            reason="A routed source explicitly states that guidance was not provided.",
        )
    return GuidanceFact(
        status=GuidanceStatus.NOT_FOUND, reason="No routed guidance/outlook source was found."
    )


def validate_guidance_required(metrics, sections: list) -> GuidanceFact:
    """Validate guidance acquisition. Set EARNINGS_DEBATE_REQUIRE_GUIDANCE=0 only for legacy tests."""
    if os.getenv("EARNINGS_DEBATE_REQUIRE_GUIDANCE", "1").strip().lower() in {"0", "false", "no"}:
        return GuidanceFact(
            status=GuidanceStatus.AMBIGUOUS, reason="Guidance gate disabled by environment."
        )
    fact = extract_guidance_fact(metrics, sections)
    if fact.status in {GuidanceStatus.FOUND, GuidanceStatus.NOT_DISCLOSED} and fact.source_refs:
        return fact
    if fact.status == GuidanceStatus.FOUND and getattr(metrics, "guidance", None):
        return fact
    raise GuidanceAcquisitionError(
        "Guidance acquisition is required. Provide a guidance/outlook source, a source-backed no-guidance disclosure, or disable only for legacy tests."
    )
