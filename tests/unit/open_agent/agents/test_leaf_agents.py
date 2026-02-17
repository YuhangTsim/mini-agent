"""Tests for open_agent leaf agents: Explorer, Librarian, Oracle, Designer, Fixer."""

from __future__ import annotations

import pytest

from open_agent.agents.designer import DesignerAgent
from open_agent.agents.explorer import ExplorerAgent
from open_agent.agents.fixer import FixerAgent
from open_agent.agents.librarian import LibrarianAgent
from open_agent.agents.oracle import OracleAgent


# ---------------------------------------------------------------------------
# Explorer
# ---------------------------------------------------------------------------


class TestExplorerAgent:
    def test_role_is_explorer(self):
        assert ExplorerAgent().role == "explorer"

    def test_is_leaf(self):
        agent = ExplorerAgent()
        assert agent.is_leaf

    def test_cannot_delegate(self):
        agent = ExplorerAgent()
        assert not agent.can_delegate("anyone")

    def test_has_read_tools(self):
        agent = ExplorerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "read_file" in allowed

    def test_has_search_tool(self):
        agent = ExplorerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "search_files" in allowed

    def test_no_write_tools(self):
        agent = ExplorerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "write_file" not in allowed
        assert "edit_file" not in allowed

    def test_system_prompt_not_empty(self):
        prompt = ExplorerAgent().get_system_prompt()
        assert len(prompt) > 0

    def test_system_prompt_mentions_search(self):
        prompt = ExplorerAgent().get_system_prompt().lower()
        assert "search" in prompt or "grep" in prompt or "glob" in prompt

    def test_model_is_gpt4o_mini(self):
        agent = ExplorerAgent()
        assert "mini" in agent.config.model


# ---------------------------------------------------------------------------
# Librarian
# ---------------------------------------------------------------------------


class TestLibrarianAgent:
    def test_role_is_librarian(self):
        assert LibrarianAgent().role == "librarian"

    def test_is_leaf(self):
        assert LibrarianAgent().is_leaf

    def test_cannot_delegate(self):
        assert not LibrarianAgent().can_delegate("anyone")

    def test_has_report_result_tool(self):
        agent = LibrarianAgent()
        allowed, _ = agent.get_tool_filter()
        assert "report_result" in allowed

    def test_system_prompt_not_empty(self):
        assert len(LibrarianAgent().get_system_prompt()) > 0


# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


class TestOracleAgent:
    def test_role_is_oracle(self):
        assert OracleAgent().role == "oracle"

    def test_cannot_delegate_to_anyone_by_default(self):
        agent = OracleAgent()
        assert not agent.can_delegate("explorer")
        assert not agent.can_delegate("fixer")

    def test_is_leaf(self):
        assert OracleAgent().is_leaf

    def test_has_read_tools(self):
        agent = OracleAgent()
        allowed, _ = agent.get_tool_filter()
        assert "read_file" in allowed
        assert "search_files" in allowed

    def test_no_write_tools(self):
        agent = OracleAgent()
        allowed, _ = agent.get_tool_filter()
        assert "write_file" not in allowed

    def test_system_prompt_not_empty(self):
        assert len(OracleAgent().get_system_prompt()) > 0


# ---------------------------------------------------------------------------
# Designer
# ---------------------------------------------------------------------------


class TestDesignerAgent:
    def test_role_is_designer(self):
        assert DesignerAgent().role == "designer"

    def test_is_leaf(self):
        assert DesignerAgent().is_leaf

    def test_cannot_delegate(self):
        assert not DesignerAgent().can_delegate("anyone")

    def test_has_report_result_tool(self):
        agent = DesignerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "report_result" in allowed

    def test_system_prompt_not_empty(self):
        assert len(DesignerAgent().get_system_prompt()) > 0


# ---------------------------------------------------------------------------
# Fixer
# ---------------------------------------------------------------------------


class TestFixerAgent:
    def test_role_is_fixer(self):
        assert FixerAgent().role == "fixer"

    def test_is_leaf(self):
        assert FixerAgent().is_leaf

    def test_cannot_delegate(self):
        assert not FixerAgent().can_delegate("anyone")

    def test_has_file_ops(self):
        agent = FixerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "read_file" in allowed
        assert "write_file" in allowed

    def test_no_delegation_tools(self):
        agent = FixerAgent()
        allowed, _ = agent.get_tool_filter()
        assert "delegate_task" not in allowed

    def test_system_prompt_not_empty(self):
        assert len(FixerAgent().get_system_prompt()) > 0


# ---------------------------------------------------------------------------
# Common leaf agent properties
# ---------------------------------------------------------------------------


class TestLeafAgentCommon:
    @pytest.mark.parametrize(
        "agent_class",
        [ExplorerAgent, LibrarianAgent, DesignerAgent, FixerAgent, OracleAgent],
    )
    def test_leaf_agents_cannot_delegate(self, agent_class):
        agent = agent_class()
        assert agent.is_leaf
        assert not agent.can_delegate("any_role")

    @pytest.mark.parametrize(
        "agent_class",
        [ExplorerAgent, LibrarianAgent, DesignerAgent, FixerAgent, OracleAgent],
    )
    def test_all_agents_have_role(self, agent_class):
        agent = agent_class()
        assert agent.role
        assert isinstance(agent.role, str)

    @pytest.mark.parametrize(
        "agent_class",
        [ExplorerAgent, LibrarianAgent, DesignerAgent, FixerAgent, OracleAgent],
    )
    def test_all_agents_produce_system_prompt(self, agent_class):
        agent = agent_class()
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50  # Must be substantive
