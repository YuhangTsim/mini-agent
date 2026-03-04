"""Integration-style tests for Settings -> ProviderRegistry wiring."""

from __future__ import annotations

import pytest

from open_agent.config.settings import Settings
from open_agent.providers import registry


def test_settings_wiring_uses_env_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakeProvider:
        def __init__(self, *, api_key: str, **kwargs: object) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(registry, "OpenAIProvider", FakeProvider)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")

    settings = Settings._from_dict({"provider": {"name": "openai", "api_key": ""}})
    provider_registry = registry.ProviderRegistry(settings.provider)
    provider_registry.get_provider(settings.agents["orchestrator"])

    assert captured["api_key"] == "sk-from-env"


def test_settings_wiring_uses_placeholder_for_base_url_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class FakeProvider:
        def __init__(self, *, api_key: str, **kwargs: object) -> None:
            captured["api_key"] = api_key

    monkeypatch.setattr(registry, "OpenAIProvider", FakeProvider)

    settings = Settings._from_dict(
        {
            "provider": {
                "name": "custom",
                "api_key": "",
                "base_url": "https://private.example/v1",
            }
        }
    )
    provider_registry = registry.ProviderRegistry(settings.provider)
    provider_registry.get_provider(settings.agents["orchestrator"])

    assert captured["api_key"] == "no-key-required"
