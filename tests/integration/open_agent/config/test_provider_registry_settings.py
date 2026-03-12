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


def test_provider_config_loads_model_from_config() -> None:
    """ProviderConfig should load model from [provider] section in config."""
    settings = Settings._from_dict(
        {"provider": {"name": "openai", "api_key": "", "model": "gpt-4o-mini"}}
    )
    assert settings.provider.model == "gpt-4o-mini"


def test_default_model_is_gpt_4_1() -> None:
    """Default model should be gpt-4.1 when not specified anywhere."""
    settings = Settings._from_dict({})
    assert settings.provider.model == "gpt-4.1"


def test_agent_uses_provider_model_as_fallback() -> None:
    """Agents should use provider.model when they don't specify their own model."""
    settings = Settings._from_dict(
        {
            "provider": {"model": "gpt-4o-mini"},
            "open_agent": {
                "agents": {
                    "orchestrator": {}  # No model specified
                }
            },
        }
    )
    # Verify provider has the specified model
    assert settings.provider.model == "gpt-4o-mini"
    # Verify orchestrator inherits the provider's model
    assert settings.agents["orchestrator"].model == "gpt-4o-mini"


def test_per_agent_model_override() -> None:
    """Per-agent model in config should take precedence over provider.model."""
    settings = Settings._from_dict(
        {
            "provider": {"model": "gpt-4o"},
            "open_agent": {
                "agents": {
                    "orchestrator": {"model": "gpt-4o-mini"}  # Override provider model
                }
            },
        }
    )
    # Provider is gpt-4o but agent override is gpt-4o-mini
    assert settings.provider.model == "gpt-4o"
    assert settings.agents["orchestrator"].model == "gpt-4o-mini"


def test_all_agents_use_provider_model_when_no_explicit_config() -> None:
    """All agents from DEFAULT_AGENTS should use provider.model when not in config."""
    settings = Settings._from_dict(
        {
            "provider": {"model": "gpt-4o-mini"},
            # No open_agent.agents section - all agents come from DEFAULT_AGENTS
        }
    )
    # Verify provider model
    assert settings.provider.model == "gpt-4o-mini"
    # Verify all default agents use the provider's model
    for role, agent_config in settings.agents.items():
        assert agent_config.model == "gpt-4o-mini", f"Agent {role} should use provider.model"


def test_compaction_uses_provider_model_fallback() -> None:
    """CompactionSettings should use provider.model when not explicitly configured."""
    settings = Settings._from_dict(
        {
            "provider": {"model": "gpt-4o"},
        }
    )
    assert settings.compaction.model == "gpt-4o"


def test_compaction_model_override() -> None:
    """CompactionSettings model can be explicitly overridden."""
    settings = Settings._from_dict(
        {"provider": {"model": "gpt-4o"}, "open_agent": {"compaction": {"model": "gpt-4o-mini"}}}
    )
    assert settings.compaction.model == "gpt-4o-mini"
