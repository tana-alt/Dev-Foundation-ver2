from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

MAX_QUERY_LENGTH = 500
MAX_SNIPPET_LENGTH = 1_200
MAX_SOURCE_REFS = 20
ALLOWED_TRANSPORTS = ("mcp", "cli", "http_health")
RESULT_STATUSES = {"ok", "blocked", "error"}
DENIED_CONTEXT = {
    "vault",
    "corpus",
    "qdrant",
    "local_paths",
    "raw_source",
    "raw_logs",
    "secrets",
    "vectors",
    "embeddings",
    "runtime_state",
    "model_memory_fallback",
}
FORBIDDEN_TEXT_MARKERS = (
    "/Users/",
    "/private/",
    "/tmp/",
    "file://",
    "qdrant",
    "vault",
    "corpus",
    "BEGIN PRIVATE KEY",
    "api_key",
    "access_token",
    "secret",
    "password",
    "raw_log",
    "raw_source",
)


class ContextValidationError(ValueError):
    """Raised when a CommonDB context request or result crosses the repo boundary."""


@dataclass(frozen=True)
class ContextSnippet:
    source_ref: str
    text: str
    relevance: str


@dataclass(frozen=True)
class ContextRequest:
    request_id: str
    workflow_ref: str
    query: str
    source_refs: tuple[str, ...]
    denied_context: tuple[str, ...]
    transport_order: tuple[str, ...]
    max_snippets: int


@dataclass(frozen=True)
class ContextResult:
    result_id: str
    request_id: str
    status: Literal["ok", "blocked", "error"]
    source_refs: tuple[str, ...]
    snippets: tuple[ContextSnippet, ...]
    error_code: str | None
    error_message: str | None


class CommonDBContextClient(Protocol):
    def fetch_context(self, request: ContextRequest) -> dict[str, Any]:
        """Return a serialized CommonDB context result."""


def validate_context_request(data: dict[str, Any]) -> ContextRequest:
    _require_value(data.get("schema_version") == "0.1", "schema_version must be 0.1")
    _require_value(data.get("record_type") == "context_request", "record_type mismatch")

    request_id = _required_string(data, "request_id")
    workflow_ref = _required_string(data, "workflow_ref")
    query = _required_string(data, "query")
    source_refs = tuple(_required_string_list(data, "source_refs"))
    denied_context = tuple(_required_string_list(data, "denied_context"))
    transport_order = tuple(_required_string_list(data, "transport_order"))
    max_snippets = _required_int(data, "max_snippets")

    _require_value(len(query) <= MAX_QUERY_LENGTH, "query is too large")
    _require_value(0 < len(source_refs) <= MAX_SOURCE_REFS, "source_refs count is invalid")
    _require_value(0 < max_snippets <= 10, "max_snippets must be between 1 and 10")
    _require_value(transport_order[0] == "mcp", "mcp must be the primary transport")
    _require_value("cli" in transport_order, "cli fallback is required")
    _require_value(
        all(transport in ALLOWED_TRANSPORTS for transport in transport_order),
        "transport_order contains unsupported transport",
    )
    _require_value(
        DENIED_CONTEXT.issubset(set(denied_context)),
        "denied_context must include all CommonDB boundary categories",
    )

    _reject_forbidden_text((request_id, workflow_ref, query, *source_refs))

    return ContextRequest(
        request_id=request_id,
        workflow_ref=workflow_ref,
        query=query,
        source_refs=source_refs,
        denied_context=denied_context,
        transport_order=transport_order,
        max_snippets=max_snippets,
    )


def validate_context_result(data: dict[str, Any]) -> ContextResult:
    _require_value(data.get("schema_version") == "0.1", "schema_version must be 0.1")
    _require_value(data.get("record_type") == "context_result", "record_type mismatch")

    result_id = _required_string(data, "result_id")
    request_id = _required_string(data, "request_id")
    status = _required_string(data, "status")
    source_refs = tuple(_required_string_list(data, "source_refs"))
    snippets_data = data.get("snippets")
    _require_value(isinstance(snippets_data, list), "snippets must be a list")
    snippet_items = cast(list[Any], snippets_data)
    error = data.get("error")
    _require_value(isinstance(error, dict), "error must be a mapping")
    error_data = cast(dict[str, Any], error)

    _require_value(status in RESULT_STATUSES, "status must be ok, blocked, or error")
    _require_value(0 < len(source_refs) <= MAX_SOURCE_REFS, "source_refs count is invalid")

    snippets: list[ContextSnippet] = []
    for snippet_data in snippet_items:
        _require_value(isinstance(snippet_data, dict), "snippet must be a mapping")
        snippet = cast(dict[str, Any], snippet_data)
        source_ref = _required_string(snippet, "source_ref")
        text = _required_string(snippet, "text")
        relevance = _required_string(snippet, "relevance")
        _require_value(source_ref in source_refs, "snippet source_ref must be declared")
        _require_value(len(text) <= MAX_SNIPPET_LENGTH, "snippet is too large")
        _reject_forbidden_text((source_ref, text, relevance))
        snippets.append(ContextSnippet(source_ref=source_ref, text=text, relevance=relevance))

    error_code = error_data.get("code")
    error_message = error_data.get("message")
    if status == "ok":
        _require_value(bool(snippets), "ok context_result requires snippets")
        _require_value(
            error_code is None and error_message is None, "ok result must not carry error"
        )
    else:
        _require_value(
            isinstance(error_code, str) and bool(error_code.strip()),
            "blocked/error code required",
        )
        _require_value(
            isinstance(error_message, str) and bool(error_message.strip()),
            "blocked/error message required",
        )
        _reject_forbidden_text((error_code, error_message))

    _reject_forbidden_text((result_id, request_id, *source_refs))

    return ContextResult(
        result_id=result_id,
        request_id=request_id,
        status=cast(Literal["ok", "blocked", "error"], status),
        source_refs=source_refs,
        snippets=tuple(snippets),
        error_code=cast(str | None, error_code),
        error_message=cast(str | None, error_message),
    )


def fetch_sanitized_context(
    client: CommonDBContextClient,
    request_data: dict[str, Any],
) -> ContextResult:
    request = validate_context_request(request_data)
    result_data = client.fetch_context(request)
    return validate_context_result(result_data)


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    _require_value(
        isinstance(value, str) and bool(value.strip()),
        f"{key} must be a non-empty string",
    )
    return cast(str, value)


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    _require_value(isinstance(value, int), f"{key} must be an integer")
    return cast(int, value)


def _required_string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    _require_value(
        isinstance(value, list) and bool(value),
        f"{key} must be a non-empty list",
    )
    values = cast(list[Any], value)
    _require_value(
        all(isinstance(item, str) and bool(item.strip()) for item in values),
        f"{key} must contain only non-empty strings",
    )
    return cast(list[str], values)


def _reject_forbidden_text(values: tuple[str | None, ...]) -> None:
    for value in values:
        if value is None:
            continue
        lowered = value.lower()
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker.lower() in lowered:
                raise ContextValidationError(f"forbidden boundary marker found: {marker}")


def _require_value(condition: bool, message: str) -> None:
    if not condition:
        raise ContextValidationError(message)
