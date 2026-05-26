"""LLM provider abstraction.

Supports Anthropic and OpenAI via a single interface so the rest of the
codebase is provider-agnostic. The choice is controlled by the
`LLM_PROVIDER` environment variable (twelve-factor: config in env).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        ...


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        from anthropic import Anthropic
        self.client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return LLMResponse(
            text=resp.content[0].text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        from openai import OpenAI
        self.client = OpenAI()  # picks up OPENAI_API_KEY from env
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")

    def complete(self, system, user, max_tokens=2048, temperature=0.7):
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )


def get_provider() -> LLMProvider:
    """Factory: chooses provider based on LLM_PROVIDER env var."""
    name = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if name == "anthropic":
        return AnthropicProvider()
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")
