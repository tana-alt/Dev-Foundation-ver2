"""Numeric grounding validation for material claims."""

from __future__ import annotations

import os
import re
from typing import Iterable


class NumericGroundingError(ValueError):
    """Raised when a material claim lacks a value, disclosed number, or caveat."""


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
    if os.getenv("EARNINGS_DEBATE_REQUIRE_NUMERIC_GROUNDING", "1").strip().lower() in {
        "0",
        "false",
        "no",
    }:
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
