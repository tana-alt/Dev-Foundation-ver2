from __future__ import annotations

import pytest

from src.workflow_adapters.commondb_context_adapter import (
    ContextRequest,
    ContextValidationError,
    fetch_sanitized_context,
    validate_context_request,
    validate_context_result,
)


def valid_request() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": "context_request",
        "request_id": "context-request-test-001",
        "workflow_ref": "work-contract-test-001",
        "query": "Provide bounded context for the adapter contract.",
        "source_refs": ["commondb:demo-context:adapter-contract"],
        "max_snippets": 2,
        "transport_order": ["mcp", "cli", "http_health"],
        "denied_context": [
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
        ],
    }


def valid_result() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "record_type": "context_result",
        "result_id": "context-result-test-001",
        "request_id": "context-request-test-001",
        "status": "ok",
        "source_refs": ["commondb:demo-context:adapter-contract"],
        "snippets": [
            {
                "source_ref": "commondb:demo-context:adapter-contract",
                "relevance": "Confirms safe bounded context.",
                "text": "A stable source reference and short sanitized summary are available.",
            }
        ],
        "error": {"code": None, "message": None},
    }


def test_request_requires_mcp_primary_and_cli_fallback() -> None:
    request = validate_context_request(valid_request())

    assert request.transport_order == ("mcp", "cli", "http_health")


def test_request_rejects_http_as_primary_transport() -> None:
    request = valid_request()
    request["transport_order"] = ["http_health", "cli"]

    with pytest.raises(ContextValidationError, match="mcp must be the primary"):
        validate_context_request(request)


def test_request_rejects_boundary_marker_in_source_refs() -> None:
    request = valid_request()
    request["source_refs"] = ["/Users/example/private-note.md"]

    with pytest.raises(ContextValidationError, match="forbidden boundary marker"):
        validate_context_request(request)


def test_result_accepts_bounded_snippet() -> None:
    result = validate_context_result(valid_result())

    assert result.status == "ok"
    assert result.snippets[0].source_ref == "commondb:demo-context:adapter-contract"


def test_result_rejects_raw_source_marker_in_snippet() -> None:
    result = valid_result()
    result["snippets"] = [
        {
            "source_ref": "commondb:demo-context:adapter-contract",
            "relevance": "Unsafe snippet.",
            "text": "raw_source: full private body",
        }
    ]

    with pytest.raises(ContextValidationError, match="forbidden boundary marker"):
        validate_context_result(result)


def test_blocked_result_is_valid_workflow_context() -> None:
    result = valid_result()
    result["status"] = "blocked"
    result["snippets"] = []
    result["error"] = {"code": "context_unavailable", "message": "Context source unavailable."}

    blocked = validate_context_result(result)

    assert blocked.status == "blocked"
    assert blocked.error_code == "context_unavailable"


def test_fetch_sanitized_context_uses_mock_client() -> None:
    class MockClient:
        def fetch_context(self, request: ContextRequest) -> dict[str, object]:
            assert request.request_id == "context-request-test-001"
            return valid_result()

    result = fetch_sanitized_context(MockClient(), valid_request())

    assert result.result_id == "context-result-test-001"
