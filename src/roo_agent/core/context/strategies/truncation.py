"""Sliding window truncation strategy for context management."""

from __future__ import annotations

from roo_agent.config.settings import ContextConfig
from roo_agent.core.context.token_manager import TokenManager
from roo_agent.persistence.models import Message, MessageRole
from roo_agent.persistence.store import Store


class TruncationStrategy:
    """Non-destructive truncation using a sliding window approach.

    Original messages remain in the database but are marked as hidden.
    A truncation marker message indicates what was hidden.
    """

    def __init__(self, config: ContextConfig, token_manager: TokenManager, store: Store):
        self.config = config
        self.token_manager = token_manager
        self.store = store

    async def truncate(
        self,
        messages: list[Message],
        task_id: str,
    ) -> list[Message]:
        """Truncate messages using sliding window, keeping recent messages.

        Returns the visible messages after truncation (including marker).
        """
        keep_count = self.config.keep_recent_messages
        if len(messages) <= keep_count:
            return messages

        # Split into messages to keep and messages to truncate
        to_truncate = messages[:-keep_count]
        to_keep = messages[-keep_count:]

        if not to_truncate:
            return messages

        # Mark truncated messages with their parent reference
        # The last message before the window becomes the truncation parent
        truncation_parent = to_truncate[-1] if to_truncate else None

        # Create a truncation marker message
        truncated_count = len(to_truncate)
        marker_content = (
            f"[{truncated_count} earlier messages hidden. "
            f"Last visible message from {truncation_parent.role.value} at "
            f"{truncation_parent.created_at.isoformat() if truncation_parent else 'unknown'}]"
        )

        marker = Message(
            task_id=task_id,
            role=MessageRole.SYSTEM,
            content=marker_content,
            is_truncation_marker=True,
            truncation_parent_id=truncation_parent.id if truncation_parent else None,
        )

        # Save the marker to the database
        await self.store.add_message(marker)

        # Update truncated messages to reference the marker
        for msg in to_truncate:
            msg.truncation_parent_id = marker.id
            await self.store.update_message(msg)

        # Return messages to keep + marker
        return [marker] + to_keep

    async def get_visible_messages(self, task_id: str) -> list[Message]:
        """Get messages excluding hidden/truncated ones."""
        return await self.store.get_visible_messages(task_id)

    async def restore_messages(self, task_id: str) -> list[Message]:
        """Restore all messages by removing truncation markers and parent references."""
        all_messages = await self.store.get_messages(task_id)

        for msg in all_messages:
            if msg.is_truncation_marker or msg.truncation_parent_id:
                # Delete truncation markers
                if msg.is_truncation_marker:
                    await self.store.delete_message(msg.id)
                # Clear parent references
                else:
                    msg.truncation_parent_id = None
                    await self.store.update_message(msg)

        return await self.store.get_messages(task_id)
