from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.llm import AnthropicProvider, OpenAIProvider, ProviderCallError, get_provider


class _StructuredPayload(BaseModel):
    verdict: str


class _FakeUsage:
    prompt_tokens = 3
    completion_tokens = 5


class _FakeMessage:
    def __init__(self, content: str = "{}") -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str = "{}") -> None:
        self.message = _FakeMessage(content)


class _FakeCompletions:
    def __init__(self) -> None:
        self.params = None
        self.parse_params = None

    def create(self, **params):
        self.params = params
        content = '{"verdict":"good"}' if "response_format" in params else "{}"
        return type(
            "FakeResponse",
            (),
            {"choices": [_FakeChoice(content)], "usage": _FakeUsage()},
        )()

    def parse(self, **params):
        self.parse_params = params
        message = SimpleNamespace(parsed=_StructuredPayload(verdict="good"), content=None)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], usage=_FakeUsage())


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = _FakeChat()


def _provider(model: str) -> tuple[OpenAIProvider, _FakeClient]:
    provider = OpenAIProvider.__new__(OpenAIProvider)
    client = _FakeClient()
    provider.client = client  # type: ignore[assignment]
    provider.model = model
    return provider, client


def test_openai_provider_uses_minimum_max_completion_tokens_for_gpt5_models():
    provider, client = _provider("gpt-5.4-mini")

    provider.complete("system", "user", max_tokens=123, temperature=0.2)

    params = client.chat.completions.params
    assert params["max_completion_tokens"] == 4096
    assert "max_tokens" not in params
    assert "temperature" not in params


def test_openai_provider_keeps_max_tokens_for_legacy_chat_models():
    provider, client = _provider("gpt-4o")

    provider.complete("system", "user", max_tokens=123, temperature=0.2)

    params = client.chat.completions.params
    assert params["max_tokens"] == 123
    assert params["temperature"] == 0.2
    assert "max_completion_tokens" not in params


def test_openai_provider_uses_structured_json_schema_response_format():
    provider, client = _provider("gpt-5.4-mini")

    response = provider.complete_structured(
        "system",
        "user",
        _StructuredPayload,
        max_tokens=123,
        temperature=0.2,
    )

    params = client.chat.completions.params
    assert params["response_format"]["type"] == "json_schema"
    assert params["response_format"]["json_schema"]["name"] == "_StructuredPayload"
    assert params["response_format"]["json_schema"]["strict"] is True
    assert params["max_completion_tokens"] == 4096
    assert response.text == '{"verdict":"good"}'


def test_openai_structured_output_removes_unsupported_schema_format():
    from src.workflow_models import BullCase, EarningsQualityFinding

    provider, client = _provider("gpt-4o")

    provider.complete_structured("system", "user", EarningsQualityFinding)

    schema_text = str(client.chat.completions.params["response_format"])
    assert "'format': 'uri'" not in schema_text
    assert "'format': 'date'" not in schema_text
    assert "propertyNames" not in schema_text

    provider.complete_structured("system", "user", BullCase)

    response_format = client.chat.completions.params["response_format"]
    schema_text = str(response_format)
    assert "propertyNames" not in schema_text
    assert "minProperties" not in schema_text
    assert "maxProperties" not in schema_text
    finding_coverage = response_format["json_schema"]["schema"]["properties"]["finding_coverage"]
    assert set(finding_coverage["properties"]) == {
        "earnings_quality",
        "cash_flow_risk",
        "management_intent",
        "guidance",
    }
    assert finding_coverage["additionalProperties"] is False


def test_openai_structured_output_fails_fast_on_request_error_by_default():
    provider, client = _provider("gpt-4o")

    def fail_create(**params):
        if "response_format" in params:
            raise RuntimeError("unsupported structured output")
        client.chat.completions.params = params
        return SimpleNamespace(choices=[_FakeChoice("{}")], usage=_FakeUsage())

    client.chat.completions.create = fail_create  # type: ignore[method-assign]

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete_structured(
            "system",
            "user",
            _StructuredPayload,
            max_tokens=123,
            temperature=0.2,
        )

    assert exc_info.value.provider == "openai"
    assert exc_info.value.model == "gpt-4o"
    assert exc_info.value.stage == "structured_call"
    assert "unsupported structured output" in str(exc_info.value)
    assert client.chat.completions.params is None


def test_openai_structured_output_optional_fallback_records_diagnostics(monkeypatch):
    monkeypatch.setenv("EARNINGS_DEBATE_STRUCTURED_FALLBACK", "1")
    provider, client = _provider("gpt-4o")

    def fail_create(**params):
        if "response_format" in params:
            raise RuntimeError("unsupported structured output")
        client.chat.completions.params = params
        return SimpleNamespace(choices=[_FakeChoice("{}")], usage=_FakeUsage())

    client.chat.completions.create = fail_create  # type: ignore[method-assign]

    response = provider.complete_structured(
        "system",
        "user",
        _StructuredPayload,
        max_tokens=123,
        temperature=0.2,
    )

    assert response.text == "{}"
    assert response.metadata["structured_fallback_used"] is True
    assert response.metadata["structured_fallback_stage"] == "structured_call"
    assert response.metadata["structured_fallback_error_type"] == "RuntimeError"
    assert response.metadata["provider"] == "openai"
    assert response.metadata["model"] == "gpt-4o"
    assert client.chat.completions.params["max_tokens"] == 123


def test_openai_structured_output_fails_when_parsed_output_is_missing():
    provider, client = _provider("gpt-4o")

    def create_without_text(**params):
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], usage=_FakeUsage())

    client.chat.completions.create = create_without_text  # type: ignore[method-assign]

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete_structured(
            "system",
            "user",
            _StructuredPayload,
            max_tokens=123,
            temperature=0.2,
        )

    assert exc_info.value.provider == "openai"
    assert exc_info.value.stage == "structured_response"
    assert "unexpected shape" in str(exc_info.value)


def test_openai_structured_output_optional_fallback_records_response_stage(monkeypatch):
    monkeypatch.setenv("EARNINGS_DEBATE_STRUCTURED_FALLBACK", "1")
    provider, client = _provider("gpt-4o")

    def create_without_text(**params):
        message = SimpleNamespace(content=None)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], usage=_FakeUsage())

    client.chat.completions.create = create_without_text  # type: ignore[method-assign]

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete_structured(
            "system",
            "user",
            _StructuredPayload,
            max_tokens=123,
            temperature=0.2,
        )

    assert exc_info.value.stage == "structured_response"


class _FakeAnthropicMessages:
    def __init__(self) -> None:
        self.create_params = None
        self.parse_params = None

    def create(self, **params):
        self.create_params = params
        content = [SimpleNamespace(text="{}")]
        usage = SimpleNamespace(input_tokens=7, output_tokens=11)
        return SimpleNamespace(content=content, usage=usage)

    def parse(self, **params):
        self.parse_params = params
        content = [SimpleNamespace(parsed_output=_StructuredPayload(verdict="good"))]
        usage = SimpleNamespace(input_tokens=7, output_tokens=11)
        return SimpleNamespace(content=content, usage=usage)


class _FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = _FakeAnthropicMessages()


def _anthropic_provider() -> tuple[AnthropicProvider, _FakeAnthropicClient]:
    provider = AnthropicProvider.__new__(AnthropicProvider)
    client = _FakeAnthropicClient()
    provider.client = client  # type: ignore[assignment]
    provider.model = "claude-sonnet-4-5"
    return provider, client


def test_anthropic_provider_uses_structured_parse_with_output_model():
    provider, client = _anthropic_provider()

    response = provider.complete_structured(
        "system",
        "user",
        _StructuredPayload,
        max_tokens=123,
        temperature=0.2,
    )

    params = client.messages.parse_params
    assert params["output_format"] is _StructuredPayload
    assert params["max_tokens"] == 123
    assert response.text == '{"verdict":"good"}'


def test_anthropic_structured_output_fails_fast_on_parse_error_by_default():
    provider, client = _anthropic_provider()

    def fail_parse(**params):
        raise RuntimeError("unsupported structured output")

    client.messages.parse = fail_parse  # type: ignore[method-assign]

    with pytest.raises(ProviderCallError) as exc_info:
        provider.complete_structured(
            "system",
            "user",
            _StructuredPayload,
            max_tokens=123,
            temperature=0.2,
        )

    assert exc_info.value.provider == "anthropic"
    assert exc_info.value.model == "claude-sonnet-4-5"
    assert exc_info.value.stage == "structured_call"
    assert client.messages.create_params is None


def test_get_provider_wraps_provider_initialization_errors(monkeypatch):
    def fail_provider():
        raise RuntimeError("missing API key")

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setattr("src.llm.OpenAIProvider", fail_provider)

    with pytest.raises(ProviderCallError) as exc_info:
        get_provider()

    assert exc_info.value.provider == "openai"
    assert exc_info.value.model == "gpt-test"
    assert exc_info.value.stage == "provider_init"
    assert "missing API key" in str(exc_info.value)
