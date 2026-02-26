"""Tests for open-agent-show-prompt CLI."""

from unittest.mock import patch, MagicMock

from mini_agent.scripts.open_agent_show_prompt import (
    get_available_agents,
    build_agent_prompt,
    list_agents,
    main,
    AGENT_CLASSES,
)


class TestGetAvailableAgents:
    """Tests for get_available_agents function."""

    @patch.dict(
        "mini_agent.scripts.open_agent_show_prompt.AGENT_CLASSES",
        {
            "orchestrator": MagicMock(),
            "explorer": MagicMock(),
        },
        clear=True
    )
    def test_returns_agent_dict(self):
        """Should return dictionary of agent names to descriptions."""
        # Setup mock agent instances
        mock_agent1 = MagicMock()
        mock_agent1.config.role_definition = "Orchestrator agent description"

        mock_agent2 = MagicMock()
        mock_agent2.config.role_definition = "Explorer agent description"

        # Setup mock classes to return instances
        AGENT_CLASSES["orchestrator"].return_value = mock_agent1
        AGENT_CLASSES["explorer"].return_value = mock_agent2

        result = get_available_agents()

        assert "orchestrator" in result
        assert "explorer" in result
        assert result["orchestrator"] == "Orchestrator agent description"
        assert result["explorer"] == "Explorer agent description"

    @patch.dict(
        "mini_agent.scripts.open_agent_show_prompt.AGENT_CLASSES",
        {},
        clear=True
    )
    def test_empty_agents(self):
        """Should handle empty agents."""
        result = get_available_agents()

        assert result == {}


class TestBuildAgentPrompt:
    """Tests for build_agent_prompt function."""

    @patch("mini_agent.scripts.open_agent_show_prompt.os.getcwd")
    def test_builds_prompt_for_valid_agent(self, mock_getcwd):
        """Should build and return prompt for valid agent."""
        mock_getcwd.return_value = "/test/dir"

        # Create a mock agent class
        mock_agent = MagicMock()
        mock_agent.get_system_prompt.return_value = "Generated prompt text"
        mock_agent_class = MagicMock(return_value=mock_agent)

        with patch.dict(
            "mini_agent.scripts.open_agent_show_prompt.AGENT_CLASSES",
            {"orchestrator": mock_agent_class},
            clear=True
        ):
            result = build_agent_prompt("orchestrator")

        assert result == "Generated prompt text"
        mock_agent.get_system_prompt.assert_called_once_with(
            context={"working_directory": "/test/dir"}
        )

    def test_returns_none_for_invalid_agent(self):
        """Should return None for unknown agent."""
        with patch.dict(
            "mini_agent.scripts.open_agent_show_prompt.AGENT_CLASSES",
            {},
            clear=True
        ):
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
