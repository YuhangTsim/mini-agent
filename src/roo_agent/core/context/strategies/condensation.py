"""AI-powered condensation strategy for context management."""

from __future__ import annotations

from roo_agent.config.settings import ContextConfig
from roo_agent.persistence.models import Message, MessageRole, ConversationSummary
from roo_agent.persistence.store import Store
from agent_kernel.providers.base import BaseProvider


# Summary prompt template
SUMMARY_PROMPT = """You are a helpful assistant that summarizes conversation history.
Your task is to create a concise summary of the following conversation messages.
Include:
1. The main topics discussed
2. Key decisions or actions taken
3. Any important context that would be needed to continue the conversation

Keep the summary brief but informative. Do not include any preamble - just the summary.

Conversation messages:
{messages}

Summary:"""


class CondensationStrategy:
    """AI-powered summarization strategy for context management.

    Uses an LLM to summarize older messages and replace them with a summary.
    Maintains chain of custody by linking to original messages.
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

    async def generate_summary(self, messages: list[Message]) -> str:
        """Generate a summary of the given messages using the LLM."""
        if not messages:
            return ""

        # Format messages for the summary prompt
        formatted_messages = []
        for msg in messages:
            role = msg.role.value
            content = msg.content[:500]  # Truncate very long messages
            formatted_messages.append(f"{role}: {content}")

        messages_text = "\n\n".join(formatted_messages)
        prompt = SUMMARY_PROMPT.format(messages=messages_text)

        # Call the LLM to generate summary
        summary_text = ""
        stream = self.provider.create_message(
            system_prompt="You are a helpful assistant that summarizes conversation history.",
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            max_tokens=1024,
            temperature=0.3,
            stream=False,  # Get complete response
        )

        # Collect the response
        async for event in stream:
            if hasattr(event, "text") and event.text:
                summary_text += event.text

        return summary_text.strip()

    async def condense(
        self,
        messages: list[Message],
        task_id: str,
    ) -> list[Message]:
        """Condense messages by generating a summary and marking originals.

        Returns the visible messages after condensation (including summary).
        """
        keep_count = self.config.keep_recent_messages
        if len(messages) <= keep_count:
            return messages

        # Split into messages to condense and messages to keep
        to_condense = messages[:-keep_count]
        to_keep = messages[-keep_count:]

        if not to_condense:
            return messages

        # Generate summary
        summary_text = await self.generate_summary(to_condense)
        if not summary_text:
            # If summary failed, fall back to truncation
            return to_keep

        # Calculate token count for summary
        token_count = self.provider.count_tokens(summary_text)

        # Create summary message
        summary_message = Message(
            task_id=task_id,
            role=MessageRole.SYSTEM,
            content=f"[Earlier conversation summary]\n\n{summary_text}",
            token_count=token_count,
            is_summary=True,
            condense_parent_id=to_condense[0].id if to_condense else None,
        )

        # Save summary message
        await self.store.add_message(summary_message)

        # Store the summary in the summaries table
        conversation_summary = ConversationSummary(
            task_id=task_id,
            message_range_start=to_condense[0].id,
            message_range_end=to_condense[-1].id,
            summary=summary_text,
            token_count=token_count,
        )
        await self.store.add_summary(conversation_summary)

        # Mark condensed messages with condense_parent_id
        for msg in to_condense:
            msg.condense_parent_id = summary_message.id
            await self.store.update_message(msg)

        # Return summary + keep messages
        return [summary_message] + to_keep

    async def get_active_summary(self, task_id: str) -> ConversationSummary | None:
        """Get the most recent summary for a task."""
        return await self.store.get_summary(task_id)

    async def expand_summary(self, task_id: str) -> list[Message]:
        """Restore original messages by removing summary and clearing references."""
        # Get all messages
        all_messages = await self.store.get_messages(task_id)

        # Find and remove summary messages
        for msg in all_messages:
            if msg.is_summary:
                # Delete the summary message
                await self.store.delete_message(msg.id)

                # Clear condense_parent_id on related messages
                related = await self.store.get_messages(task_id)
                for rel_msg in related:
                    if rel_msg.condense_parent_id == msg.id:
                        rel_msg.condense_parent_id = None
                        await self.store.update_message(rel_msg)

        # Delete conversation summaries for this task
        summaries = await self.store.get_summaries(task_id)
        for summary in summaries:
            await self.store.delete_summary(summary.id)

        return await self.store.get_messages(task_id)
