"""Tests for open-agent-show-prompt CLI."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mini_agent.scripts.open_agent_show_prompt import (
    get_available_agents,
    build_agent_prompt,
    list_agents,
    main,
)


class TestGetAvailableAgents:
    """Tests for get_available_agents function."""

    @patch("mini_agent.scripts.open_agent_show_prompt.Settings")
    def test_returns_agent_dict(self, mock_settings_class):
        """Should return dictionary of agent names to descriptions."""
        # Setup mock config
        mock_config1 = Mock()
        mock_config1.role_definition = "Orchestrator agent description"

        mock_config2 = Mock()
        mock_config2.role_definition = "Explorer agent description"

        # Setup mock settings
        mock_settings = Mock()
        mock_settings.agents = {
            "orchestrator": mock_config1,
            "explorer": mock_config2,
        }
        mock_settings_class.return_value = mock_settings

        result = get_available_agents()

        assert "orchestrator" in result
        assert "explorer" in result
        assert result["orchestrator"] == "Orchestrator agent description"
        assert result["explorer"] == "Explorer agent description"

    @patch("mini_agent.scripts.open_agent_show_prompt.Settings")
    def test_empty_agents(self, mock_settings_class):
        """Should handle empty agents."""
        mock_settings = Mock()
        mock_settings.agents = {}
        mock_settings_class.return_value = mock_settings

        result = get_available_agents()

        assert result == {}


class TestBuildAgentPrompt:
    """Tests for build_agent_prompt function."""

    @patch("mini_agent.scripts.open_agent_show_prompt.Settings")
    @patch("mini_agent.scripts.open_agent_show_prompt.PromptBuilder")
    @patch("mini_agent.scripts.open_agent_show_prompt.ToolRegistry")
    @patch("mini_agent.scripts.open_agent_show_prompt.get_all_native_tools")
    def test_builds_prompt_for_valid_agent(
        self, mock_get_tools, mock_tool_registry_class, mock_builder_class, mock_settings_class
    ):
        """Should build and return prompt for valid agent."""
        # Setup mock settings
        mock_config = Mock()
        mock_config.allowed_tools = ["read_file", "search_files"]

        mock_settings = Mock()
        mock_settings.agents = {"orchestrator": mock_config}
        mock_settings_class.return_value = mock_settings

        # Setup mock tools
        mock_tool = Mock()
        mock_get_tools.return_value = [mock_tool]

        mock_tool_registry = Mock()
        mock_tool_registry.get.return_value = mock_tool
        mock_tool_registry_class.return_value = mock_tool_registry

        # Setup mock builder
        mock_builder = Mock()
        mock_builder.build.return_value = "Generated prompt text"
        mock_builder_class.return_value = mock_builder

        result = build_agent_prompt("orchestrator")

        assert result == "Generated prompt text"
        mock_builder.build.assert_called_once()

    @patch("mini_agent.scripts.open_agent_show_prompt.Settings")
    def test_returns_none_for_invalid_agent(self, mock_settings_class):
        """Should return None for unknown agent."""
        mock_settings = Mock()
        mock_settings.agents = {}
        mock_settings_class.return_value = mock_settings

        result = build_agent_prompt("unknown_agent")

        assert result is None


class TestListAgents:
    """Tests for list_agents function."""

    @patch("mini_agent.scripts.open_agent_show_prompt.get_available_agents")
    def test_prints_agents(self, mock_get_agents, capsys):
        """Should print list of available agents."""
        mock_get_agents.return_value = {
            "orchestrator": "Orchestrator description",
            "explorer": "Explorer description",
        }

        list_agents()

        captured = capsys.readouterr()
        assert "Available open-agent agents:" in captured.out
        assert "orchestrator" in captured.out
        assert "explorer" in captured.out
        assert "--agent" in captured.out

    @patch("mini_agent.scripts.open_agent_show_prompt.get_available_agents")
    def test_handles_empty_agents(self, mock_get_agents, capsys):
        """Should handle empty agent list."""
        mock_get_agents.return_value = {}

        list_agents()

        captured = capsys.readouterr()
        assert "No agents found" in captured.out


class TestMain:
    """Tests for main CLI entry point."""

    @patch("mini_agent.scripts.open_agent_show_prompt.list_agents")
    def test_no_args_lists_agents(self, mock_list_agents):
        """Should list agents when no --agent argument provided."""
        result = main([])

        assert result == 0
        mock_list_agents.assert_called_once()

    @patch("mini_agent.scripts.open_agent_show_prompt.build_agent_prompt")
    def test_valid_agent_prints_prompt(self, mock_build_prompt, capsys):
        """Should print prompt for valid agent."""
        mock_build_prompt.return_value = "Full prompt text"

        result = main(["--agent", "orchestrator"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Full prompt text" in captured.out

    @patch("mini_agent.scripts.open_agent_show_prompt.build_agent_prompt")
    @patch("mini_agent.scripts.open_agent_show_prompt.list_agents")
    def test_invalid_agent_shows_error(self, mock_list_agents, mock_build_prompt):
        """Should show error and list agents for invalid agent."""
        mock_build_prompt.return_value = None

        result = main(["--agent", "invalid_agent"])

        assert result == 1
        mock_list_agents.assert_called_once()
