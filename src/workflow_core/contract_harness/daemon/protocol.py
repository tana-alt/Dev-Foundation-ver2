from __future__ import annotations

from typing import Any

from pydantic import Field

from workflow_core.contract_harness.domain.models import StrictModel


class DaemonRequest(StrictModel):
    schema_version: int = 1
    request_id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    capability_token: str | None = None


class DaemonErrorPayload(StrictModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class DaemonResponse(StrictModel):
    schema_version: int = 1
    request_id: str
    ok: bool
    result: dict[str, Any] | None = None
    error: DaemonErrorPayload | None = None


def ok_response(request_id: str, result: dict[str, Any] | None = None) -> DaemonResponse:
    return DaemonResponse(request_id=request_id, ok=True, result=result or {})


def error_response(
    request_id: str,
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> DaemonResponse:
    return DaemonResponse(
        request_id=request_id,
        ok=False,
        error=DaemonErrorPayload(code=code, message=message, details=details or {}),
    )
