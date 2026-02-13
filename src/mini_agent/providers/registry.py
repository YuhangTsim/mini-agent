"""Provider factory/registry."""

from __future__ import annotations

from ..config.settings import ProviderConfig
from .base import BaseProvider
from .openai import OpenAIProvider


_PROVIDERS: dict[str, type] = {
    "openai": OpenAIProvider,
}


def create_provider(config: ProviderConfig) -> BaseProvider:
    """Create a provider instance from config."""
    api_key = config.resolve_api_key()
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{config.name}'. "
            f"Set it in config or via environment variable."
        )

    if config.name == "openai":
        return OpenAIProvider(
            api_key=api_key,
            model=config.model,
            base_url=config.base_url,
        )

    raise ValueError(f"Unknown provider: {config.name}. Available: {list(_PROVIDERS.keys())}")
