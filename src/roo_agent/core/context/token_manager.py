"""Token management for context-aware message handling."""

from __future__ import annotations

from agent_kernel.providers.base import BaseProvider
from roo_agent.persistence.models import Message


class TokenManager:
    """Manages token counting and context window calculations."""

    def __init__(
        self,
        provider: BaseProvider,
        max_context_tokens: int | None = None,
    ):
        self.provider = provider
        self._max_context_tokens = max_context_tokens

    @property
    def max_context_tokens(self) -> int:
        """Get the max context tokens, defaulting from provider if not set."""
        if self._max_context_tokens is not None:
            return self._max_context_tokens
        model_info = self.provider.get_model_info()
        return model_info.max_context

    async def count_message_tokens(self, message: Message) -> int:
        """Count tokens for a single message including role prefix."""
        # Include role in token count approximation
        role_prefix = f"{message.role.value}: "
        content = role_prefix + message.content
        return self.provider.count_tokens(content)

    async def count_messages_tokens(self, messages: list[Message]) -> int:
        """Count total tokens for a list of messages."""
        total = 0
        for msg in messages:
            total += await self.count_message_tokens(msg)
        return total

    async def count_messages_dict_tokens(self, messages: list[dict[str, str]]) -> int:
        """Count tokens for messages in dict format (like OpenAI API)."""
        total = 0
        for msg in messages:
            # Format similar to OpenAI API
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Add overhead for role and structure
            formatted = f"{role}: {content}"
            total += self.provider.count_tokens(formatted)
        return total

    async def get_available_tokens(self, system_prompt: str) -> int:
        """Calculate available tokens after system prompt."""
        system_tokens = self.provider.count_tokens(system_prompt)
        return max(0, self.max_context_tokens - system_tokens)

    async def needs_truncation(
        self,
        messages: list[Message],
        system_prompt: str,
        threshold: float = 0.9,
    ) -> bool:
        """Check if messages need truncation based on token threshold."""
        total_tokens = await self.count_messages_tokens(messages)
        system_tokens = self.provider.count_tokens(system_prompt)
        total_context = system_tokens + total_tokens

        return total_context > (self.max_context_tokens * threshold)

    async def get_token_usage(
        self,
        messages: list[Message],
        system_prompt: str,
    ) -> dict[str, int]:
        """Get detailed token usage breakdown."""
        system_tokens = self.provider.count_tokens(system_prompt)
        message_tokens = await self.count_messages_tokens(messages)
        total = system_tokens + message_tokens

        return {
            "system": system_tokens,
            "messages": message_tokens,
            "total": total,
            "max": self.max_context_tokens,
            "available": max(0, self.max_context_tokens - total),
            "usage_percent": (total / self.max_context_tokens * 100) if self.max_context_tokens > 0 else 0,
        }
