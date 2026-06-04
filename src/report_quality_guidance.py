"""Guidance acquisition classification.

Guidance detection is a routing and missing-data signal by default. Strict
validation remains available for callers that explicitly require source-backed
guidance or a source-backed no-guidance disclosure.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Literal

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
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_refs: list[SourceRef] = Field(default_factory=list)
    candidate_section_ids: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    matched_signal_strength: Literal["none", "weak", "strong"] = "none"
    reason: str | None = None


STRONG_GUIDANCE_TERMS = (
    "financial outlook",
    "business outlook",
    "provided guidance",
    "guidance",
    "outlook",
    "forecast",
    "next quarter",
    "full year",
)
NO_GUIDANCE_TERMS = (
    "does not provide guidance",
    "not providing guidance",
    "no guidance",
    "withdrawn guidance",
    "suspended guidance",
)
WEAK_GUIDANCE_TERMS = (
    "forward-looking statements",
    "forward looking statements",
    "long-term target",
    "long term target",
    "strategy",
    "roadmap",
)

STRONG_GUIDANCE_RE = re.compile(
    r"\b(financial\s+outlook|business\s+outlook|provided\s+guidance|guidance|outlook|forecast|next\s+quarter|full\s+year)\b",
    re.IGNORECASE,
)
NO_GUIDANCE_RE = re.compile(
    r"\b(does\s+not\s+provide\s+guidance|not\s+providing\s+guidance|no\s+guidance|withdrawn\s+guidance|suspended\s+guidance)\b",
    re.IGNORECASE,
)
WEAK_GUIDANCE_RE = re.compile(
    r"\b(forward[- ]looking\s+statements?|long[- ]term\s+targets?|strategy|roadmap)\b",
    re.IGNORECASE,
)


def classify_guidance_sources(metrics, sections: list) -> GuidanceFact:
    guidance_text = getattr(metrics, "guidance", None)
    metric_refs = list(getattr(metrics, "source_refs", []) or [])
    if isinstance(guidance_text, str) and guidance_text.strip():
        return GuidanceFact(
            status=GuidanceStatus.FOUND,
            confidence=0.9,
            source_refs=metric_refs,
            matched_terms=_matched_terms(guidance_text, STRONG_GUIDANCE_TERMS),
            matched_signal_strength="strong",
            reason="Structured financial metrics include guidance text.",
        )

    guidance_matches: list[tuple[SourceRef, str, list[str]]] = []
    no_guidance_matches: list[tuple[SourceRef, str, list[str]]] = []
    weak_matches: list[tuple[SourceRef, str, list[str]]] = []
    for section in sections:
        heading = getattr(section, "heading", "") or ""
        text = getattr(section, "text", "") or ""
        haystack = f"{heading}\n{text}"
        ref = getattr(section, "source_ref", None)
        section_id = _section_id(section, ref)
        if ref is None or section_id is None:
            continue
        no_guidance_terms = _matched_terms(haystack, NO_GUIDANCE_TERMS)
        if no_guidance_terms and NO_GUIDANCE_RE.search(haystack):
            no_guidance_matches.append((ref, section_id, no_guidance_terms))
            continue
        guidance_terms = _matched_terms(haystack, STRONG_GUIDANCE_TERMS)
        if guidance_terms and STRONG_GUIDANCE_RE.search(haystack):
            guidance_matches.append((ref, section_id, guidance_terms))
            continue
        weak_terms = _matched_terms(haystack, WEAK_GUIDANCE_TERMS)
        if weak_terms and WEAK_GUIDANCE_RE.search(haystack):
            weak_matches.append((ref, section_id, weak_terms))

    if guidance_matches:
        return GuidanceFact(
            status=GuidanceStatus.FOUND,
            confidence=0.82,
            source_refs=_unique_refs(match[0] for match in guidance_matches),
            candidate_section_ids=_unique_strings(match[1] for match in guidance_matches),
            matched_terms=_unique_terms(term for match in guidance_matches for term in match[2]),
            matched_signal_strength="strong",
            reason="Source text contains guidance or outlook language.",
        )
    if no_guidance_matches:
        return GuidanceFact(
            status=GuidanceStatus.NOT_DISCLOSED,
            confidence=0.86,
            source_refs=_unique_refs(match[0] for match in no_guidance_matches),
            candidate_section_ids=_unique_strings(match[1] for match in no_guidance_matches),
            matched_terms=_unique_terms(term for match in no_guidance_matches for term in match[2]),
            matched_signal_strength="strong",
            reason="A routed source explicitly states that guidance was not provided.",
        )
    if weak_matches:
        return GuidanceFact(
            status=GuidanceStatus.AMBIGUOUS,
            confidence=0.35,
            source_refs=_unique_refs(match[0] for match in weak_matches),
            candidate_section_ids=_unique_strings(match[1] for match in weak_matches),
            matched_terms=_unique_terms(term for match in weak_matches for term in match[2]),
            matched_signal_strength="weak",
            reason="Only weak guidance-like language was found.",
        )
    return GuidanceFact(
        status=GuidanceStatus.NOT_FOUND,
        confidence=0.0,
        matched_signal_strength="none",
        reason="No routed guidance/outlook source was found.",
    )


def extract_guidance_fact(metrics, sections: list) -> GuidanceFact:
    return classify_guidance_sources(metrics, sections)


def validate_guidance_required(metrics, sections: list) -> GuidanceFact:
    """Strict guidance validation for opt-in callers."""
    if os.getenv("EARNINGS_DEBATE_REQUIRE_GUIDANCE", "1").strip().lower() in {"0", "false", "no"}:
        return GuidanceFact(
            status=GuidanceStatus.AMBIGUOUS,
            confidence=0.0,
            reason="Guidance gate disabled by environment.",
        )
    fact = classify_guidance_sources(metrics, sections)
    if fact.status in {GuidanceStatus.FOUND, GuidanceStatus.NOT_DISCLOSED} and fact.source_refs:
        return fact
    if fact.status == GuidanceStatus.FOUND and getattr(metrics, "guidance", None):
        return fact
    raise GuidanceAcquisitionError(
        "Guidance acquisition is required. Provide a guidance/outlook source, a source-backed no-guidance disclosure, or disable only for legacy tests."
    )


def _section_id(section, ref: SourceRef | None) -> str | None:
    section_id = getattr(section, "section_id", None)
    if section_id:
        return str(section_id)
    if ref is not None and ref.section_id:
        return ref.section_id
    return None


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def _unique_refs(refs) -> list[SourceRef]:
    seen: set[tuple] = set()
    result: list[SourceRef] = []
    for ref in refs:
        key = (
            ref.source_id,
            ref.source_type.value,
            ref.document_id,
            ref.section_id,
            ref.metric_name,
            ref.page,
            ref.title,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def _unique_strings(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _unique_terms(values) -> list[str]:
    return _unique_strings(values)
