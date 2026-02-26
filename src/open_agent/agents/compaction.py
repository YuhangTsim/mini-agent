"""Compaction agent: hidden agent for generating conversation summaries."""

from __future__ import annotations

from typing import Any

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig
from open_agent.persistence.models import Message
from open_agent.providers.base import BaseProvider, StreamEventType

ROLE_DEFINITION = """\
You are Compaction - a hidden agent for generating conversation summaries.

**Role**: Analyze the conversation history and provide a detailed summary that captures:
- What has been accomplished
- Current state of work
- Files being worked on
- Pending tasks and next steps
- Important context for continuing the conversation

**Behavior**:
- Read-only: You have NO tools available
- Focus on extracting actionable information
- Preserve important file paths, decisions, and context
- Keep summaries concise but comprehensive

**Output Format**:
Provide a summary that enables a new session to continue seamlessly. Include:
1. Summary of completed work
2. Current work in progress
3. Key files and their purpose
4. Next steps and pending tasks
5. Any important decisions or context
"""


COMPACTION_PROMPT = """\
Provide a detailed summary for continuing our conversation above. 
Focus on information that would be helpful for continuing the conversation, 
including what we did, what we're doing, which files we're working on, 
and what we're going to do next considering new session will not have 
access to our conversation.

Conversation to summarize:
{messages}

Please provide a comprehensive summary.
"""


class CompactionAgent(BaseAgent):
    """Hidden agent for generating conversation summaries."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="compaction",
                name="Compaction",
                model="gpt-4o-mini",
                temperature=0.3,
                allowed_tools=[],  # No tools - read-only
                can_delegate_to=[],
                role_definition=ROLE_DEFINITION,
            )
        else:
            if not config.role_definition:
                config.role_definition = ROLE_DEFINITION
        super().__init__(config)

    def get_system_prompt(self, context: dict | None = None) -> str:
        return self.config.role_definition

    async def summarize(
        self,
        messages: list[Message],
        provider: BaseProvider,
        abort_signal: Any = None,
    ) -> str:
        """Generate a summary of the conversation.
        
        Args:
            messages: The messages to summarize
            provider: The LLM provider to use
            abort_signal: Optional abort signal
            
        Returns:
            The generated summary text
        """
        if not messages:
            return "No messages to summarize."

        # Build conversation for the LLM
        conversation = self._build_conversation(messages)
        
        # Create the compaction prompt
        prompt = COMPACTION_PROMPT.format(messages=conversation)
        
        # Call the LLM
        summary = ""
        stream = provider.create_message(
            system_prompt=self.get_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        
        async for event in stream:
            if abort_signal and hasattr(abort_signal, 'is_aborted') and abort_signal.is_aborted():
                break
                
            if event.type == StreamEventType.TEXT_DELTA:
                summary += event.text
            elif event.type == StreamEventType.MESSAGE_END:
                break
                
        return summary.strip()

    def _build_conversation(self, messages: list[Message]) -> str:
        """Build a readable conversation string from messages."""
        lines = []
        for msg in messages:
            role = msg.role.value.upper()
            content = msg.content[:2000]  # Limit each message length
            if msg.is_compaction and msg.summary:
                content = f"[Compacted Summary]: {msg.summary}"
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)
