"""Provider registry for per-agent model selection."""

from __future__ import annotations

from open_agent.config.agents import AgentConfig
from open_agent.config.settings import ProviderConfig
from open_agent.providers.base import BaseProvider
from open_agent.providers.openai import OpenAIProvider


class ProviderRegistry:
    """Creates and caches provider instances per (provider_name, model) pair.

    Different agents can use different models — the registry ensures we reuse
    provider instances when two agents share the same model config.
    """

    def __init__(self, provider_config: ProviderConfig) -> None:
        self._provider_config = provider_config
        self._cache: dict[str, BaseProvider] = {}

    def get_provider(self, agent_config: AgentConfig) -> BaseProvider:
        """Get or create a provider for the given agent config."""
        cache_key = f"{self._provider_config.name}:{agent_config.model}"

        if cache_key not in self._cache:
            api_key = self._provider_config.resolve_api_key()
            if not api_key:
                raise ValueError(
                    f"No API key found for provider '{self._provider_config.name}'. "
                    f"Set the appropriate environment variable."
                )
            self._cache[cache_key] = OpenAIProvider(
                api_key=api_key,
                model=agent_config.model,
                base_url=self._provider_config.base_url,
                provider_name=self._provider_config.name,
            )

        return self._cache[cache_key]
