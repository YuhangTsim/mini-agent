"""Provider factory/registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import PROVIDER_MODELS, BaseProvider, ModelInfo
from .openai import OpenAIProvider

if TYPE_CHECKING:
    from roo_agent.config.settings import ProviderConfig


_PROVIDERS: dict[str, type] = {
    "openai": OpenAIProvider,
}


def create_provider(config: "ProviderConfig") -> BaseProvider:
    """Create a provider instance from config.

    Any provider with a base_url or name "openai" uses the OpenAI-compatible client.
    For non-OpenAI compatible providers, an API key is required.
    """
    api_key = config.resolve_api_key()

    if config.is_openai_compatible:
        return OpenAIProvider(
            api_key=api_key or "no-key-required",
            model=config.model,
            base_url=config.base_url,
            max_context=config.max_context,
            max_output=config.max_output,
            provider_name=config.name,
        )

    if not api_key:
        raise ValueError(
            f"No API key found for provider '{config.name}'. "
            f"Set it in config or via environment variable."
        )

    raise ValueError(
        f"Unknown provider: {config.name}. Available: openai (or any OpenAI-compatible with base_url)"
    )


def list_models(provider_name: str) -> list[ModelInfo]:
    """Return available models for a provider."""
    return PROVIDER_MODELS.get(provider_name, [])
