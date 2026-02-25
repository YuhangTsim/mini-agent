"""Tests for compaction agent."""

from __future__ import annotations

import pytest

from open_agent.agents.compaction import CompactionAgent, COMPACTION_PROMPT
from open_agent.config.agents import AgentConfig
from open_agent.persistence.models import Message, MessageRole


class TestCompactionAgent:
    """Test CompactionAgent."""

    def test_compaction_agent_default_config(self):
        """Test CompactionAgent with default config."""
        agent = CompactionAgent()
        
        assert agent.role == "compaction"
        assert agent.name == "Compaction"
        assert agent.config.model == "gpt-4o-mini"
        assert agent.config.temperature == 0.3
        assert agent.config.allowed_tools == []
        assert agent.config.can_delegate_to == []

    def test_compaction_agent_custom_config(self):
        """Test CompactionAgent with custom config."""
        config = AgentConfig(
            role="compaction",
            name="CustomCompaction",
            model="gpt-4o",
            temperature=0.5,
        )
        agent = CompactionAgent(config)
        
        assert agent.role == "compaction"
        assert agent.config.model == "gpt-4o"
        assert agent.config.temperature == 0.5

    def test_compaction_agent_system_prompt(self):
        """Test CompactionAgent system prompt."""
        agent = CompactionAgent()
        prompt = agent.get_system_prompt()
        
        assert "Compaction" in prompt
        assert "summary" in prompt.lower()

    def test_build_conversation_empty(self):
        """Test building conversation from empty messages."""
        agent = CompactionAgent()
        result = agent._build_conversation([])
        
        assert result == ""

    def test_build_conversation_single_message(self):
        """Test building conversation from single message."""
        agent = CompactionAgent()
        messages = [
            Message(
                agent_run_id="run-1",
                role=MessageRole.USER,
                content="Hello",
            ),
        ]
        result = agent._build_conversation(messages)
        
        assert "USER: Hello" in result

    def test_build_conversation_multiple_messages(self):
        """Test building conversation from multiple messages."""
        agent = CompactionAgent()
        messages = [
            Message(agent_run_id="run-1", role=MessageRole.USER, content="Hi"),
            Message(agent_run_id="run-1", role=MessageRole.ASSISTANT, content="Hello"),
            Message(agent_run_id="run-1", role=MessageRole.USER, content="How are you?"),
        ]
        result = agent._build_conversation(messages)
        
        assert "USER: Hi" in result
        assert "ASSISTANT: Hello" in result
        assert "USER: How are you?" in result

    def test_build_conversation_truncates_long_content(self):
        """Test that long message content is truncated."""
        agent = CompactionAgent()
        long_content = "x" * 3000
        messages = [
            Message(
                agent_run_id="run-1",
                role=MessageRole.USER,
                content=long_content,
            ),
        ]
        result = agent._build_conversation(messages)
        
        # Should be truncated to 2000
        assert len(result) < 2500

    def test_build_conversation_compaction_message(self):
        """Test building conversation with compaction message."""
        agent = CompactionAgent()
        messages = [
            Message(
                agent_run_id="run-1",
                role=MessageRole.SYSTEM,
                content="Old content",
                is_compaction=True,
                summary="This is a summary of previous conversation",
            ),
        ]
        result = agent._build_conversation(messages)
        
        assert "[Compacted Summary]: This is a summary of previous conversation" in result


class TestCompactionPrompt:
    """Test compaction prompt template."""

    def test_compaction_prompt_has_placeholder(self):
        """Test that prompt template has message placeholder."""
        assert "{messages}" in COMPACTION_PROMPT

    def test_compaction_prompt_format(self):
        """Test formatting compaction prompt."""
        messages = "USER: Hello\nASSISTANT: Hi"
        result = COMPACTION_PROMPT.format(messages=messages)
        
        assert messages in result
        assert "summary" in result.lower()
