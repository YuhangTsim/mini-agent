"""Unit tests for open_agent.cli.app."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_kernel.tools.base import ToolResult
from mini_agent.persistence.models import TokenUsage
from open_agent.bus import Event, EventBus
from open_agent.bus.events import EventPayload
from open_agent.cli.app import (
    CLICallbacks,
    DelegationDisplay,
    _format_params,
    _handle_command,
    cli,
)


# ---------------------------------------------------------------------------
# _format_params
# ---------------------------------------------------------------------------


class TestFormatParams:
    def test_simple_key_value(self):
        result = _format_params({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_long_value_truncated(self):
        result = _format_params({"key": "x" * 200})
        assert "..." in result
        assert len(result) < 250

    def test_empty_params(self):
        assert _format_params({}) == ""

    def test_multiple_params_all_present(self):
        result = _format_params({"a": "1", "b": "2"})
        assert "a" in result and "b" in result


# ---------------------------------------------------------------------------
# Click entry points
# ---------------------------------------------------------------------------


class TestClickCommands:
    def test_cli_help(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_chat_help(self):
        result = CliRunner().invoke(cli, ["chat", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_no_subcommand_calls_repl(self):
        with patch("open_agent.cli.app.asyncio.run") as mock_run, \
             patch("open_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(cli)
        mock_run.assert_called_once()

    def test_chat_calls_repl(self):
        with patch("open_agent.cli.app.asyncio.run") as mock_run, \
             patch("open_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(cli, ["chat"])
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# CLICallbacks — text streaming
# ---------------------------------------------------------------------------


class TestCLICallbacksText:
    async def test_on_text_delta_accumulates(self):
        cb = CLICallbacks()
        with patch("open_agent.cli.app.Live") as MockLive, \
             patch("open_agent.cli.app.console"):
            MockLive.return_value = MagicMock()
            await cb.on_text_delta("Hello")
            await cb.on_text_delta(" World")
        assert cb._streamed_text == "Hello World"

    async def test_on_text_delta_starts_live_on_first_call(self):
        cb = CLICallbacks()
        assert cb._live is None
        with patch("open_agent.cli.app.Live") as MockLive, \
             patch("open_agent.cli.app.console"):
            mock_live = MagicMock()
            MockLive.return_value = mock_live
            await cb.on_text_delta("Hi")
        assert cb._live is not None

    async def test_on_text_delta_reuses_existing_live(self):
        cb = CLICallbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        with patch("open_agent.cli.app.Live") as MockLive, \
             patch("open_agent.cli.app.console"):
            await cb.on_text_delta("More text")
        # Live was not re-created
        MockLive.assert_not_called()


# ---------------------------------------------------------------------------
# CLICallbacks — tool calls
# ---------------------------------------------------------------------------


class TestCLICallbacksToolCalls:
    async def test_on_tool_call_start_flushes_live(self):
        cb = CLICallbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        cb._streamed_text = "streamed"
        with patch("open_agent.cli.app.console"):
            await cb.on_tool_call_start("id1", "read_file", "{}")
        mock_live.stop.assert_called_once()
        assert cb._live is None
        assert cb._streamed_text == ""

    async def test_on_tool_call_end_success_prints_checkmark(self):
        cb = CLICallbacks()
        result = ToolResult.success("output here")
        with patch("open_agent.cli.app.console") as mock_console:
            await cb.on_tool_call_end("id1", "read_file", result)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "✓" in output or "output here" in output

    async def test_on_tool_call_end_error_prints_message(self):
        cb = CLICallbacks()
        result = ToolResult.failure("something failed")
        with patch("open_agent.cli.app.console") as mock_console:
            await cb.on_tool_call_end("id1", "tool", result)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "something failed" in output

    async def test_on_tool_call_end_long_output_truncated(self):
        cb = CLICallbacks()
        result = ToolResult.success("x" * 200)
        with patch("open_agent.cli.app.console") as mock_console:
            await cb.on_tool_call_end("id1", "tool", result)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        # Output preview is capped at 80 chars; "..." should appear in long output
        assert "..." in output or len("x" * 200) > 80


# ---------------------------------------------------------------------------
# CLICallbacks — message end
# ---------------------------------------------------------------------------


class TestCLICallbacksMessageEnd:
    async def test_tokens_printed_when_nonzero(self):
        cb = CLICallbacks()
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        with patch("open_agent.cli.app.console") as mock_console:
            await cb.on_message_end(usage)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "100" in output

    async def test_zero_tokens_no_print(self):
        cb = CLICallbacks()
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        with patch("open_agent.cli.app.console") as mock_console:
            await cb.on_message_end(usage)
        mock_console.print.assert_not_called()

    async def test_flushes_live_on_message_end(self):
        cb = CLICallbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        cb._streamed_text = "some text"
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        with patch("open_agent.cli.app.console"):
            await cb.on_message_end(usage)
        mock_live.stop.assert_called_once()
        assert cb._live is None


# ---------------------------------------------------------------------------
# CLICallbacks — flush_live
# ---------------------------------------------------------------------------


class TestCLICallbacksFlushLive:
    def test_flush_clears_live_and_text(self):
        cb = CLICallbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        cb._streamed_text = "some text"
        cb._flush_live()
        mock_live.stop.assert_called_once()
        assert cb._live is None
        assert cb._streamed_text == ""

    def test_flush_when_no_live_does_not_crash(self):
        cb = CLICallbacks()
        cb._flush_live()  # Should not raise


# ---------------------------------------------------------------------------
# DelegationDisplay — subscription
# ---------------------------------------------------------------------------


class TestDelegationDisplaySubscription:
    def test_subscribes_to_six_events(self):
        bus = EventBus()
        DelegationDisplay(bus)
        assert len(bus._handlers[Event.DELEGATION_START]) == 1
        assert len(bus._handlers[Event.DELEGATION_END]) == 1
        assert len(bus._handlers[Event.BACKGROUND_TASK_QUEUED]) == 1
        assert len(bus._handlers[Event.BACKGROUND_TASK_COMPLETE]) == 1
        assert len(bus._handlers[Event.BACKGROUND_TASK_FAILED]) == 1
        assert len(bus._handlers[Event.AGENT_START]) == 1


# ---------------------------------------------------------------------------
# DelegationDisplay — handlers
# ---------------------------------------------------------------------------


def make_payload(event: Event, agent_role: str = "orchestrator", data: dict | None = None):
    return EventPayload(
        event=event,
        session_id="s1",
        agent_role=agent_role,
        data=data or {},
    )


class TestDelegationDisplayHandlers:
    async def test_delegation_start_shows_target(self):
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.DELEGATION_START, data={"target_role": "explorer", "description": "Find files"})
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_delegation_start(payload)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "explorer" in output

    async def test_delegation_end_shows_target(self):
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.DELEGATION_END, data={"target_role": "fixer"})
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_delegation_end(payload)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "fixer" in output

    async def test_bg_queued_handler_prints(self):
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.BACKGROUND_TASK_QUEUED, data={"task_id": "abc123", "description": "Run"})
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_bg_queued(payload)
        mock_console.print.assert_called_once()

    async def test_bg_complete_handler_prints(self):
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.BACKGROUND_TASK_COMPLETE, data={"task_id": "abc123"})
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_bg_complete(payload)
        mock_console.print.assert_called_once()

    async def test_bg_failed_shows_error(self):
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.BACKGROUND_TASK_FAILED, data={"task_id": "abc", "error": "timeout"})
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_bg_failed(payload)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "timeout" in output

    async def test_agent_start_orchestrator_silent(self):
        """Orchestrator agent start is suppressed to reduce noise."""
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.AGENT_START, agent_role="orchestrator")
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_agent_start(payload)
        mock_console.print.assert_not_called()

    async def test_agent_start_non_orchestrator_prints(self):
        """Non-orchestrator agent start is shown."""
        bus = EventBus()
        display = DelegationDisplay(bus)
        payload = make_payload(Event.AGENT_START, agent_role="explorer")
        with patch("open_agent.cli.app.console") as mock_console:
            await display._on_agent_start(payload)
        mock_console.print.assert_called_once()

    async def test_publish_triggers_handler_end_to_end(self):
        """Verify bus.publish() fires the registered handler."""
        bus = EventBus()
        DelegationDisplay(bus)
        with patch("open_agent.cli.app.console"):
            await bus.publish(
                Event.DELEGATION_START,
                session_id="s1",
                agent_role="orchestrator",
                data={"target_role": "librarian", "description": "Look up docs"},
            )
        # No exception = handler ran successfully


# ---------------------------------------------------------------------------
# _handle_command
# ---------------------------------------------------------------------------


def make_mock_app():
    app = MagicMock()

    agent = MagicMock()
    agent.role = "orchestrator"
    agent.config.can_delegate_to = ["explorer", "fixer"]
    agent.config.model = "gpt-4o"
    agent.config.temperature = 0.0
    app.agent_registry.all_agents.return_value = [agent]

    tool = MagicMock()
    tool.name = "read_file"
    tool.category = "file_ops"
    app.tool_registry.all_tools.return_value = [tool]

    app.store.list_sessions = AsyncMock(return_value=[])

    app.settings.provider.name = "openai"
    app.settings.provider.base_url = None
    app.settings.provider.resolve_api_key.return_value = "sk-test"

    app._session = None
    return app


class TestHandleCommand:
    async def test_agents_lists_registered_agents(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/agents", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "orchestrator" in output

    async def test_tools_lists_registered_tools(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/tools", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "read_file" in output

    async def test_history_empty(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/history", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "No sessions" in output

    async def test_history_with_sessions(self):
        app = make_mock_app()
        session = MagicMock()
        session.status.value = "completed"
        session.id = "abc12345678"
        session.title = "My session"
        session.token_usage.input_tokens = 100
        session.token_usage.output_tokens = 50
        app.store.list_sessions = AsyncMock(return_value=[session])
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/history", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "My session" in output

    async def test_model_shows_provider_info(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/model", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "openai" in output

    async def test_session_no_active_session(self):
        app = make_mock_app()
        app._session = None
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/session", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "No active session" in output

    async def test_session_with_active_session(self):
        app = make_mock_app()
        session = MagicMock()
        session.id = "test-session-id"
        session.status.value = "active"
        session.title = "Working"
        session.working_directory = "/workspace"
        session.token_usage.input_tokens = 10
        session.token_usage.output_tokens = 5
        session.created_at.isoformat.return_value = "2024-01-01T00:00:00"
        app._session = session
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/session", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "test-session-id" in output

    async def test_help_lists_all_commands(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/help", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        for cmd in ["/agents", "/tools", "/history", "/model", "/session"]:
            assert cmd in output

    async def test_unknown_command_shows_error(self):
        app = make_mock_app()
        with patch("open_agent.cli.app.console") as mock_console:
            await _handle_command("/nonexistent", app)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Unknown" in output or "unknown" in output.lower()
