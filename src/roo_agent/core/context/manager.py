"""Context manager that orchestrates truncation and condensation strategies."""

from __future__ import annotations

from roo_agent.config.settings import ContextConfig
from roo_agent.core.context.token_manager import TokenManager
from roo_agent.core.context.strategies import TruncationStrategy, CondensationStrategy
from roo_agent.persistence.models import Message
from roo_agent.persistence.store import Store
from agent_kernel.providers.base import BaseProvider


class ContextManager:
    """Orchestrates context management using truncation and/or condensation.

    The manager monitors token usage and decides when to apply context management
    based on the configured strategy:
    - "truncate": Always use sliding window truncation
    - "condense": Always use AI summarization
    - "auto": Use truncation for minor overflow, condensation for significant overflow
    """

    def __init__(
        self,
        config: ContextConfig,
        provider: BaseProvider,
        store: Store,
    ):
        self.config = config
        self.provider = provider
        self.store = store

        # Initialize token manager
        self.token_manager = TokenManager(
            provider=provider,
            max_context_tokens=config.max_context_tokens,
        )

        # Initialize strategies
        self.truncation_strategy = TruncationStrategy(
            config=config,
            token_manager=self.token_manager,
            store=store,
        )
        self.condensation_strategy = CondensationStrategy(
            config=config,
            provider=provider,
            store=store,
        )

    async def prepare_context(
        self,
        task_id: str,
        system_prompt: str,
    ) -> list[dict[str, str]]:
        """Prepare context messages for the LLM API.

        Returns messages in dict format suitable for the provider API.
        """
        if not self.config.enabled:
            # Return all messages without any management
            messages = await self.store.get_messages(task_id)
            return self._messages_to_dict(messages)

        # Get current messages
        messages = await self.store.get_messages(task_id)

        # Check if we need context management
        if not await self.token_manager.needs_truncation(
            messages,
            system_prompt,
            threshold=self.config.truncation_threshold,
        ):
            # No truncation needed
            return self._messages_to_dict(messages)

        # Apply context management based on strategy
        if self.config.strategy == "truncate":
            visible = await self.truncation_strategy.truncate(messages, task_id)
        elif self.config.strategy == "condense":
            visible = await self.condensation_strategy.condense(messages, task_id)
        else:  # "auto"
            # Use condensation for significant overflow, truncation otherwise
            usage = await self.token_manager.get_token_usage(messages, system_prompt)
            if usage["usage_percent"] > (self.config.condensation_threshold * 100):
                visible = await self.condensation_strategy.condense(messages, task_id)
            else:
                visible = await self.truncation_strategy.truncate(messages, task_id)

        return self._messages_to_dict(visible)

    async def process_new_message(self, message: Message) -> None:
        """Process a new message after it's been added.

        This can be used to trigger context management if needed.
        """
        # Currently a no-op - context management happens at prepare_context time
        pass

    async def get_active_summary(self, task_id: str) -> str | None:
        """Get the active summary text for a task if one exists."""
        summary = await self.condensation_strategy.get_active_summary(task_id)
        return summary.summary if summary else None

    async def restore_context(self, task_id: str) -> list[Message]:
        """Restore all context by removing truncation markers and summaries."""
        # First expand any summaries
        await self.condensation_strategy.expand_summary(task_id)

        # Then restore truncated messages
        return await self.truncation_strategy.restore_messages(task_id)

    def _messages_to_dict(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert Message objects to dict format for provider API."""
        result = []
        for msg in messages:
            msg_dict: dict[str, str] = {"role": msg.role.value, "content": msg.content}
            result.append(msg_dict)
        return result
