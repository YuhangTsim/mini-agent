"""Tests for open_agent.agents.base.BaseAgent."""

from __future__ import annotations

import pytest

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig


# ---------------------------------------------------------------------------
# Concrete implementation for testing
# ---------------------------------------------------------------------------


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self, context=None) -> str:
        return f"You are {self.name}. Working in: {(context or {}).get('working_directory', '.')}"


def make_agent(**kwargs) -> TestAgent:
    config = AgentConfig(role="test_agent", **kwargs)
    return ConcreteAgent(config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBaseAgentProperties:
    def test_role_from_config(self):
        agent = make_agent(name="Tester")
        assert agent.role == "test_agent"

    def test_name_from_config(self):
        agent = make_agent(name="Explorer Bot")
        assert agent.name == "Explorer Bot"

    def test_name_defaults_from_role(self):
        config = AgentConfig(role="my_agent")
        agent = ConcreteAgent(config)
        # Pydantic model_post_init capitalizes role
        assert agent.name == "My Agent"

    def test_config_accessible(self):
        agent = make_agent(model="gpt-4o-mini", temperature=0.3)
        assert agent.config.model == "gpt-4o-mini"
        assert agent.config.temperature == 0.3


class TestBaseAgentToolFilter:
    def test_empty_filter_returns_empty_lists(self):
        agent = make_agent()
        allowed, denied = agent.get_tool_filter()
        assert allowed == []
        assert denied == []

    def test_allow_list_returned(self):
        agent = make_agent(allowed_tools=["read_file", "search_files"])
        allowed, denied = agent.get_tool_filter()
        assert allowed == ["read_file", "search_files"]
        assert denied == []

    def test_deny_list_returned(self):
        agent = make_agent(denied_tools=["execute_command"])
        allowed, denied = agent.get_tool_filter()
        assert allowed == []
        assert denied == ["execute_command"]

    def test_both_allow_and_deny(self):
        agent = make_agent(
            allowed_tools=["read_file", "write_file"],
            denied_tools=["execute_command"],
        )
        allowed, denied = agent.get_tool_filter()
        assert "read_file" in allowed
        assert "write_file" in allowed
        assert "execute_command" in denied


class TestBaseAgentDelegation:
    def test_can_delegate_to_listed_agent(self):
        agent = make_agent(can_delegate_to=["explorer", "fixer"])
        assert agent.can_delegate("explorer")
        assert agent.can_delegate("fixer")

    def test_cannot_delegate_to_unlisted_agent(self):
        agent = make_agent(can_delegate_to=["explorer"])
        assert not agent.can_delegate("fixer")
        assert not agent.can_delegate("oracle")

    def test_cannot_delegate_when_list_empty(self):
        agent = make_agent(can_delegate_to=[])
        assert not agent.can_delegate("anyone")

    def test_is_leaf_when_no_delegation(self):
        agent = make_agent(can_delegate_to=[])
        assert agent.is_leaf

    def test_is_not_leaf_when_can_delegate(self):
        agent = make_agent(can_delegate_to=["explorer"])
        assert not agent.is_leaf


class TestBaseAgentSystemPrompt:
    def test_system_prompt_returned(self):
        agent = make_agent(name="Test Bot")
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_uses_context(self):
        agent = make_agent(name="Test Bot")
        prompt = agent.get_system_prompt(context={"working_directory": "/workspace"})
        assert "/workspace" in prompt

    def test_system_prompt_without_context(self):
        agent = make_agent(name="Test Bot")
        # Should not raise
        prompt = agent.get_system_prompt(context=None)
        assert isinstance(prompt, str)
