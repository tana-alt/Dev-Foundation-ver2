from __future__ import annotations

from src.llm import OpenAIProvider


class _FakeUsage:
    prompt_tokens = 3
    completion_tokens = 5


class _FakeMessage:
    content = "{}"


class _FakeChoice:
    message = _FakeMessage()


class _FakeCompletions:
    def __init__(self) -> None:
        self.params = None

    def create(self, **params):
        self.params = params
        return type(
            "FakeResponse",
            (),
            {"choices": [_FakeChoice()], "usage": _FakeUsage()},
        )()


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
