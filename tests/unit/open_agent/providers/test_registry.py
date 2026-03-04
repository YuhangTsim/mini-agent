"""Tests for open_agent.providers.registry."""

from __future__ import annotations

import pytest

from open_agent.config.agents import AgentConfig
from open_agent.config.settings import ProviderConfig
from open_agent.providers import registry


def test_uses_placeholder_key_for_base_url_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class FakeProvider:
        def __init__(self, *, api_key: str, **kwargs: object) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(registry, "OpenAIProvider", FakeProvider)

    provider_config = ProviderConfig(name="custom", base_url="https://private.example/v1")
    agent_config = AgentConfig(role="orchestrator", model="custom-model")

    provider_registry = registry.ProviderRegistry(provider_config)
    provider_registry.get_provider(agent_config)

    assert captured["api_key"] == "no-key-required"


def test_uses_resolved_api_key_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakeProvider:
        def __init__(self, *, api_key: str, **kwargs: object) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(registry, "OpenAIProvider", FakeProvider)

    provider_config = ProviderConfig(name="custom", api_key="sk-private", base_url="https://private.example/v1")
    agent_config = AgentConfig(role="orchestrator", model="custom-model")

    provider_registry = registry.ProviderRegistry(provider_config)
    provider_registry.get_provider(agent_config)

    assert captured["api_key"] == "sk-private"


def test_raises_when_no_api_key_and_no_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    provider_config = ProviderConfig(name="openai", api_key="")
    agent_config = AgentConfig(role="orchestrator", model="gpt-4o")

    provider_registry = registry.ProviderRegistry(provider_config)

    with pytest.raises(ValueError, match="No API key"):
        provider_registry.get_provider(agent_config)
