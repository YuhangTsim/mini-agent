"""Tests for open_agent.agents.orchestrator.OrchestratorAgent."""

from __future__ import annotations

import pytest

from open_agent.agents.orchestrator import OrchestratorAgent
from open_agent.config.agents import AgentConfig


class TestOrchestratorAgentDefaults:
    def test_role_is_orchestrator(self):
        agent = OrchestratorAgent()
        assert agent.role == "orchestrator"

    def test_name_is_set(self):
        agent = OrchestratorAgent()
        assert agent.name  # Not empty

    def test_can_delegate_to_all_specialists(self):
        agent = OrchestratorAgent()
        for specialist in ["explorer", "librarian", "oracle", "designer", "fixer"]:
            assert agent.can_delegate(specialist), f"Cannot delegate to {specialist}"

    def test_cannot_delegate_to_self(self):
        agent = OrchestratorAgent()
        assert not agent.can_delegate("orchestrator")

    def test_is_not_leaf(self):
        agent = OrchestratorAgent()
        assert not agent.is_leaf

    def test_has_delegation_tools(self):
        agent = OrchestratorAgent()
        allowed, _ = agent.get_tool_filter()
        assert "delegate_task" in allowed

    def test_has_background_delegation_tool(self):
        agent = OrchestratorAgent()
        allowed, _ = agent.get_tool_filter()
        assert "delegate_background" in allowed

    def test_has_report_result_tool(self):
        agent = OrchestratorAgent()
        allowed, _ = agent.get_tool_filter()
        assert "report_result" in allowed

    def test_no_file_ops_in_allowed_tools(self):
        agent = OrchestratorAgent()
        allowed, _ = agent.get_tool_filter()
        assert "read_file" not in allowed
        assert "write_file" not in allowed


class TestOrchestratorSystemPrompt:
    def test_system_prompt_is_string(self):
        agent = OrchestratorAgent()
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_system_prompt_mentions_delegation(self):
        agent = OrchestratorAgent()
        prompt = agent.get_system_prompt()
        assert "delegate" in prompt.lower() or "specialist" in prompt.lower()

    def test_system_prompt_with_working_directory(self):
        agent = OrchestratorAgent()
        prompt = agent.get_system_prompt(context={"working_directory": "/my/project"})
        assert isinstance(prompt, str)

    def test_role_definition_not_empty(self):
        agent = OrchestratorAgent()
        assert agent.config.role_definition


class TestOrchestratorCustomConfig:
    def test_custom_config_applied(self):
        config = AgentConfig(
            role="orchestrator",
            model="gpt-4-turbo",
            can_delegate_to=["explorer"],
        )
        agent = OrchestratorAgent(config)
        assert agent.config.model == "gpt-4-turbo"
        assert agent.can_delegate("explorer")
        assert not agent.can_delegate("fixer")

    def test_custom_config_preserves_role_definition(self):
        """When custom config has no role_definition, default is applied."""
        config = AgentConfig(role="orchestrator", can_delegate_to=["explorer"])
        agent = OrchestratorAgent(config)
        assert agent.config.role_definition  # Should be filled in by __init__
