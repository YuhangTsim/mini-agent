"""Tests for roo-agent-show-prompt CLI."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mini_agent.scripts.roo_agent_show_prompt import (
    get_available_modes,
    build_mode_prompt,
    list_modes_func,
    main,
)


class TestGetAvailableModes:
    """Tests for get_available_modes function."""

    @patch("mini_agent.scripts.roo_agent_show_prompt.list_modes")
    def test_returns_mode_dict(self, mock_list_modes):
        """Should return dictionary of mode slugs to descriptions."""
        mock_mode1 = Mock()
        mock_mode1.slug = "code"
        mock_mode1.when_to_use = "For writing code"

        mock_mode2 = Mock()
        mock_mode2.slug = "plan"
        mock_mode2.when_to_use = "For planning"

        mock_list_modes.return_value = [mock_mode1, mock_mode2]

        result = get_available_modes()

        assert "code" in result
        assert "plan" in result
        assert result["code"] == "For writing code"
        assert result["plan"] == "For planning"

    @patch("mini_agent.scripts.roo_agent_show_prompt.list_modes")
    def test_empty_modes(self, mock_list_modes):
        """Should handle empty modes list."""
        mock_list_modes.return_value = []

        result = get_available_modes()

        assert result == {}


class TestBuildModePrompt:
    """Tests for build_mode_prompt function."""

    @patch("mini_agent.scripts.roo_agent_show_prompt.get_mode")
    @patch("mini_agent.scripts.roo_agent_show_prompt.Settings")
    @patch("mini_agent.scripts.roo_agent_show_prompt.ToolRegistry")
    @patch("mini_agent.scripts.roo_agent_show_prompt.PromptBuilder")
    @patch("mini_agent.scripts.roo_agent_show_prompt.Task")
    def test_builds_prompt_for_valid_mode(
        self, mock_task_class, mock_builder_class, mock_tool_registry_class,
        mock_load_settings, mock_get_mode
    ):
        """Should build and return prompt for valid mode."""
        # Setup mock mode config
        mock_mode = Mock()
        mock_mode.slug = "code"
        mock_mode.tool_groups = ["read", "edit"]
        mock_get_mode.return_value = mock_mode

        # Setup mock settings
        mock_settings = Mock()
        mock_load_settings.return_value = mock_settings

        # Setup mock tools
        mock_tool = Mock()
        mock_tool_registry = Mock()
        mock_tool_registry.get_tools_by_group.return_value = [mock_tool]
        mock_tool_registry_class.return_value = mock_tool_registry

        # Setup mock builder
        mock_builder = Mock()
        mock_builder.build.return_value = "Generated prompt text"
        mock_builder_class.return_value = mock_builder

        result = build_mode_prompt("code")

        assert result == "Generated prompt text"
        mock_get_mode.assert_called_once_with("code")
        mock_builder.build.assert_called_once()

    @patch("mini_agent.scripts.roo_agent_show_prompt.get_mode")
    def test_returns_none_for_invalid_mode(self, mock_get_mode):
        """Should return None for unknown mode."""
        mock_get_mode.side_effect = KeyError("Unknown mode")

        result = build_mode_prompt("unknown_mode")

        assert result is None


class TestListModesFunc:
    """Tests for list_modes_func function."""

    @patch("mini_agent.scripts.roo_agent_show_prompt.get_available_modes")
    def test_prints_modes(self, mock_get_modes, capsys):
        """Should print list of available modes."""
        mock_get_modes.return_value = {
            "code": "For writing code",
            "plan": "For planning tasks",
        }

        list_modes_func()

        captured = capsys.readouterr()
        assert "Available roo-agent modes:" in captured.out
        assert "code" in captured.out
        assert "plan" in captured.out
        assert "--mode" in captured.out

    @patch("mini_agent.scripts.roo_agent_show_prompt.get_available_modes")
    def test_handles_empty_modes(self, mock_get_modes, capsys):
        """Should handle empty mode list."""
        mock_get_modes.return_value = {}

        list_modes_func()

        captured = capsys.readouterr()
        assert "No modes found" in captured.out


class TestMain:
    """Tests for main CLI entry point."""

    @patch("mini_agent.scripts.roo_agent_show_prompt.list_modes_func")
    def test_no_args_lists_modes(self, mock_list_modes):
        """Should list modes when no --mode argument provided."""
        result = main([])

        assert result == 0
        mock_list_modes.assert_called_once()

    @patch("mini_agent.scripts.roo_agent_show_prompt.build_mode_prompt")
    def test_valid_mode_prints_prompt(self, mock_build_prompt, capsys):
        """Should print prompt for valid mode."""
        mock_build_prompt.return_value = "Full prompt text"

        result = main(["--mode", "code"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Full prompt text" in captured.out

    @patch("mini_agent.scripts.roo_agent_show_prompt.build_mode_prompt")
    @patch("mini_agent.scripts.roo_agent_show_prompt.list_modes_func")
    def test_invalid_mode_shows_error(self, mock_list_modes, mock_build_prompt):
        """Should show error and list modes for invalid mode."""
        mock_build_prompt.return_value = None

        result = main(["--mode", "invalid_mode"])

        assert result == 1
        mock_list_modes.assert_called_once()
