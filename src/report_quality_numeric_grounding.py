"""Numeric grounding validation for material claims."""

from __future__ import annotations

import os
import re
from copy import copy
from typing import Iterable, TypeVar, cast


class NumericGroundingError(ValueError):
    """Raised when a material claim lacks a value, disclosed number, or caveat."""


T = TypeVar("T")


TRIGGER_RE = re.compile(
    r"\b(strong|large|meaningful|improved|improvement|deteriorated|beat|miss|expanded|contracted|margin|pressure|concentration|cash conversion|investment intensity|growth|decline)\b",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(
    r"(?:\$|¥|€)?\s?\d+(?:\.\d+)?\s?(?:%|bps|million|billion|m|bn|x)?", re.IGNORECASE
)
CAVEAT_TERMS = (
    "missing",
    "not routed",
    "not provided",
    "not available",
    "not disclosed",
    "not directly verified",
    "no guidance",
    "absence",
    "absent",
    "lack",
    "lacks",
    "insufficient",
    "cannot determine",
    "cannot be determined",
    "unclear",
)

NUMERIC_GROUNDING_CAVEAT = (
    "Numeric grounding caveat: numeric value was not routed for this material claim; "
    "treat it as qualitative interpretation rather than a quantified fact."
)
EVIDENCE_DETAIL_MAX_LENGTH = 1200
UNGROUNDED_EVIDENCE_CONFIDENCE_CAP = 0.45
UNGROUNDED_DECISION_CONFIDENCE_CAP = 0.55


def _source_type_value(ref) -> str:
    value = getattr(ref, "source_type", "")
    return str(getattr(value, "value", value))


def claim_requires_grounding(item) -> bool:
    text = " ".join(
        [str(getattr(item, "summary", "") or ""), str(getattr(item, "detail", "") or "")]
    )
    return bool(TRIGGER_RE.search(text))


def has_numeric_grounding(item) -> bool:
    if getattr(item, "value", None) is not None:
        return True
    if getattr(item, "metric_name", None):
        return True
    ref = getattr(item, "source_ref", None)
    if (
        ref is not None
        and _source_type_value(ref) in {"financial_api", "derived_metric"}
        and getattr(ref, "metric_name", None)
    ):
        return True
    text = " ".join(
        [str(getattr(item, "summary", "") or ""), str(getattr(item, "detail", "") or "")]
    )
    if NUMBER_RE.search(text):
        return True
    lowered = text.lower()
    if any(term in lowered for term in CAVEAT_TERMS):
        return True
    return False


def validate_numeric_grounding(items: Iterable) -> None:
    if not _numeric_grounding_required_enabled():
        return
    failures = []
    for item in items:
        if claim_requires_grounding(item) and not has_numeric_grounding(item):
            failures.append(getattr(item, "evidence_id", getattr(item, "summary", "unknown")))
    if failures:
        raise NumericGroundingError(
            "Material claims require numeric grounding or an explicit missing-data caveat: "
            + ", ".join(map(str, failures))
        )


def numeric_grounding_failures(items: Iterable) -> list[str]:
    if not _numeric_grounding_required_enabled():
        return []
    failures: list[str] = []
    for item in items:
        if claim_requires_grounding(item) and not has_numeric_grounding(item):
            failures.append(str(getattr(item, "evidence_id", getattr(item, "summary", "unknown"))))
    return failures


def apply_numeric_grounding_caveats(items: Iterable) -> tuple[list, list[str]]:
    if not _numeric_grounding_required_enabled():
        return list(items), []
    repaired: list = []
    repaired_ids: list[str] = []
    for item in items:
        if claim_requires_grounding(item) and not has_numeric_grounding(item):
            repaired.append(_copy_with_numeric_grounding_caveat(item))
            repaired_ids.append(
                str(getattr(item, "evidence_id", getattr(item, "summary", "unknown")))
            )
        else:
            repaired.append(item)
    if not repaired_ids:
        return repaired, []
    ids = ", ".join(repaired_ids)
    return repaired, [f"numeric grounding caveat applied to material evidence: {ids}"]


def apply_numeric_grounding_caveats_to_decision(decision: T) -> tuple[T, list[str]]:
    positive, positive_warnings = apply_numeric_grounding_caveats(
        getattr(decision, "positive_evidence", []) or []
    )
    negative, negative_warnings = apply_numeric_grounding_caveats(
        getattr(decision, "negative_evidence", []) or []
    )
    warnings = [*positive_warnings, *negative_warnings]
    if not warnings:
        return decision, []
    updates = {
        "positive_evidence": positive,
        "negative_evidence": negative,
        "confidence": min(
            float(getattr(decision, "confidence", 0.0) or 0.0),
            UNGROUNDED_DECISION_CONFIDENCE_CAP,
        ),
    }
    if hasattr(decision, "model_copy"):
        return cast(T, decision.model_copy(update=updates)), warnings
    repaired_decision = copy(decision)
    for key, value in updates.items():
        setattr(repaired_decision, key, value)
    return repaired_decision, warnings


def _copy_with_numeric_grounding_caveat(item):
    detail = _detail_with_numeric_grounding_caveat(str(getattr(item, "detail", "") or ""))
    confidence = min(
        float(getattr(item, "confidence", 0.0) or 0.0),
        UNGROUNDED_EVIDENCE_CONFIDENCE_CAP,
    )
    updates = {"detail": detail, "confidence": confidence}
    if hasattr(item, "model_copy"):
        return item.model_copy(update=updates)
    repaired = copy(item)
    for key, value in updates.items():
        setattr(repaired, key, value)
    return repaired


def _detail_with_numeric_grounding_caveat(detail: str) -> str:
    if NUMERIC_GROUNDING_CAVEAT.lower() in detail.lower():
        return detail[:EVIDENCE_DETAIL_MAX_LENGTH]
    separator = " " if detail else ""
    max_detail_length = EVIDENCE_DETAIL_MAX_LENGTH - len(separator) - len(NUMERIC_GROUNDING_CAVEAT)
    if max_detail_length < 0:
        return NUMERIC_GROUNDING_CAVEAT[:EVIDENCE_DETAIL_MAX_LENGTH]
    base = detail[:max_detail_length].rstrip()
    return f"{base}{separator}{NUMERIC_GROUNDING_CAVEAT}".strip()


def _numeric_grounding_required_enabled() -> bool:
    return os.getenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
