"""Tests for OpenAIProvider thinking_budget_tokens forwarding."""

from __future__ import annotations

from unittest.mock import patch


from agent_kernel.providers.openai import OpenAIProvider


def make_provider() -> OpenAIProvider:
    """Create an OpenAIProvider with a fake base_url (no API key validation)."""
    return OpenAIProvider(
        api_key="test-key",
        model="claude-sonnet-4-6",
        base_url="http://localhost:11434/v1",
        provider_name="custom",
    )


class TestOpenAIProviderThinkingBudget:
    async def test_thinking_budget_added_to_kwargs_when_set(self):
        """When thinking_budget_tokens is given, 'thinking' key is added to API call kwargs."""
        provider = make_provider()
        captured: dict = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)

            # Return an empty async iterator
            async def _empty():
                return
                yield  # make it an async generator

            return _empty()

        with patch.object(provider._client.chat.completions, "create", new=fake_create):
            stream = provider.create_message(
                system_prompt="sys",
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget_tokens=5000,
            )
            # Consume the stream
            async for _ in stream:
                pass

        assert captured.get("thinking") == {"type": "enabled", "budget_tokens": 5000}

    async def test_thinking_budget_absent_when_none(self):
        """When thinking_budget_tokens is None, 'thinking' key is NOT added to API call kwargs."""
        provider = make_provider()
        captured: dict = {}

        async def fake_create(**kwargs):
            captured.update(kwargs)

            async def _empty():
                return
                yield

            return _empty()

        with patch.object(provider._client.chat.completions, "create", new=fake_create):
            stream = provider.create_message(
                system_prompt="sys",
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget_tokens=None,
            )
            async for _ in stream:
                pass

        assert "thinking" not in captured


class TestAgentConfigThinkingBudget:
    def test_thinking_budget_defaults_to_none(self):
        from open_agent.config.agents import AgentConfig

        config = AgentConfig(role="test")
        assert config.thinking_budget_tokens is None

    def test_thinking_budget_can_be_set(self):
        from open_agent.config.agents import AgentConfig

        config = AgentConfig(role="test", thinking_budget_tokens=8000)
        assert config.thinking_budget_tokens == 8000

    def test_thinking_budget_zero_is_valid(self):
        from open_agent.config.agents import AgentConfig

        config = AgentConfig(role="test", thinking_budget_tokens=0)
        assert config.thinking_budget_tokens == 0
