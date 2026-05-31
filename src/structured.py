"""Helpers for validating structured LLM output.

LLM providers return text. The rest of the application should only see
validated Pydantic models.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


def strip_json_fence(text: str) -> str:
    """Accept bare JSON or a fenced JSON block and return the JSON payload."""
    payload = text.strip()
    if not payload.startswith("```"):
        return payload

    end = payload.rfind("```")
    if end <= 0:
        return payload

    inner = payload[3:end].strip()
    if inner.startswith("json"):
        inner = inner[4:].strip()
    return inner


def load_json(text: str) -> object:
    return json.loads(strip_json_fence(text))


def parse_model(model_type: type[ModelT], text: str) -> ModelT:
    return model_type.model_validate(load_json(text))


def parse_model_list(model_type: type[ModelT], text: str) -> list[ModelT]:
    raw = load_json(text)
    if not isinstance(raw, list):
        raise TypeError("expected a JSON array")
    return [model_type.model_validate(item) for item in raw]
