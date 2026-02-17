"""Tests for agent_kernel.providers.registry."""

from __future__ import annotations

import pytest

from agent_kernel.providers.registry import create_provider, list_models
from roo_agent.config.settings import ProviderConfig


class TestCreateProvider:
    def test_openai_provider_with_key(self):
        config = ProviderConfig(name="openai", model="gpt-4o", api_key="test-key")
        provider = create_provider(config)
        assert provider is not None

    def test_openai_compatible_with_base_url_no_key(self):
        """Any provider with base_url is treated as OpenAI-compatible."""
        config = ProviderConfig(
            name="custom",
            model="my-model",
            base_url="http://localhost:11434/v1",
        )
        provider = create_provider(config)
        assert provider is not None

    def test_openai_compatible_openrouter(self):
        config = ProviderConfig(
            name="openrouter",
            model="anthropic/claude-3-sonnet",
            api_key="sk-or-test",
            base_url="https://openrouter.ai/api/v1",
        )
        provider = create_provider(config)
        assert provider is not None

    def test_unknown_provider_without_key_raises(self):
        """Non-openai without base_url or api_key raises ValueError."""
        config = ProviderConfig(name="unknown_provider", model="some-model")
        with pytest.raises(ValueError):
            create_provider(config)

    def test_non_openai_without_key_raises(self, monkeypatch):
        """Non-openai, non-openai-compatible provider requires an API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        config = ProviderConfig(name="anthropic", model="claude-3-opus", api_key="")
        with pytest.raises(ValueError, match="No API key"):
            create_provider(config)

    def test_openai_is_openai_compatible(self):
        config = ProviderConfig(name="openai", model="gpt-4o")
        assert config.is_openai_compatible

    def test_base_url_is_openai_compatible(self):
        config = ProviderConfig(
            name="anything", model="model", base_url="http://localhost:8080"
        )
        assert config.is_openai_compatible

    def test_unknown_is_not_openai_compatible(self):
        config = ProviderConfig(name="anthropic", model="claude-3")
        assert not config.is_openai_compatible


class TestListModels:
    def test_openai_models_not_empty(self):
        models = list_models("openai")
        assert len(models) > 0

    def test_openai_contains_gpt4o(self):
        models = list_models("openai")
        model_ids = [m.model_id for m in models]
        assert "gpt-4o" in model_ids

    def test_openai_model_info_fields(self):
        models = list_models("openai")
        gpt4o = next(m for m in models if m.model_id == "gpt-4o")
        assert gpt4o.provider == "openai"
        assert gpt4o.max_context > 0
        assert gpt4o.supports_tools

    def test_unknown_provider_returns_empty(self):
        models = list_models("nonexistent_provider")
        assert models == []


class TestProviderConfig:
    def test_resolve_api_key_from_config(self):
        config = ProviderConfig(name="openai", model="gpt-4o", api_key="sk-direct")
        assert config.resolve_api_key() == "sk-direct"

    def test_resolve_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        config = ProviderConfig(name="openai", model="gpt-4o")
        assert config.resolve_api_key() == "sk-from-env"

    def test_resolve_api_key_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = ProviderConfig(name="openai", model="gpt-4o")
        assert config.resolve_api_key() is None
