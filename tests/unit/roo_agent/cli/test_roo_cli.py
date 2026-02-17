"""Unit tests for roo_agent.cli.app."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_kernel.tools.base import ToolResult
from mini_agent.persistence.models import TokenUsage
from roo_agent.cli.app import (
    CLICallbacks,
    _handle_export,
    _handle_history,
    _handle_model,
    _handle_task,
    main,
)
from roo_agent.persistence.models import Task, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_task(**kwargs) -> Task:
    defaults = dict(
        mode="code",
        status=TaskStatus.ACTIVE,
        title="Test task",
        working_directory="/tmp",
    )
    defaults.update(kwargs)
    return Task(**defaults)


def make_callbacks() -> CLICallbacks:
    return CLICallbacks(MagicMock())


# ---------------------------------------------------------------------------
# Click entry points
# ---------------------------------------------------------------------------


class TestClickCommands:
    def test_main_help(self):
        result = CliRunner().invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_chat_help(self):
        result = CliRunner().invoke(main, ["chat", "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_export_help(self):
        result = CliRunner().invoke(main, ["export", "--help"])
        assert result.exit_code == 0
        assert "TASK_ID" in result.output

    def test_serve_help(self):
        result = CliRunner().invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "port" in result.output.lower()

    def test_main_no_subcommand_calls_repl(self):
        with patch("roo_agent.cli.app.asyncio.run") as mock_run, \
             patch("roo_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(main)
        mock_run.assert_called_once()

    def test_chat_calls_repl(self):
        with patch("roo_agent.cli.app.asyncio.run") as mock_run, \
             patch("roo_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(main, ["chat"])
        mock_run.assert_called_once()

    def test_export_calls_asyncio_run(self):
        with patch("roo_agent.cli.app.asyncio.run") as mock_run, \
             patch("roo_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(main, ["export", "abc123"])
        mock_run.assert_called_once()

    def test_serve_calls_asyncio_run(self):
        mock_server_mod = MagicMock()
        mock_server_mod.run_server = AsyncMock()
        with patch.dict("sys.modules", {"roo_agent.api.http.server": mock_server_mod}), \
             patch("roo_agent.cli.app.asyncio.run") as mock_run, \
             patch("roo_agent.cli.app.Settings.load", return_value=MagicMock()):
            CliRunner().invoke(main, ["serve"])
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# CLICallbacks — text streaming
# ---------------------------------------------------------------------------


class TestCLICallbacksText:
    async def test_on_text_delta_accumulates(self):
        cb = make_callbacks()
        cb._live = MagicMock()
        with patch("roo_agent.cli.app.console"):
            await cb.on_text_delta("Hello")
            await cb.on_text_delta(" World")
        assert cb._streaming_text == "Hello World"

    async def test_on_text_delta_updates_live(self):
        cb = make_callbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        with patch("roo_agent.cli.app.console"):
            await cb.on_text_delta("Hi")
        mock_live.update.assert_called_once()

    async def test_on_text_delta_no_live_does_not_crash(self):
        cb = make_callbacks()
        cb._live = None
        with patch("roo_agent.cli.app.console"):
            await cb.on_text_delta("text")
        assert cb._streaming_text == "text"


# ---------------------------------------------------------------------------
# CLICallbacks — tool calls
# ---------------------------------------------------------------------------


class TestCLICallbacksToolCalls:
    async def test_on_tool_call_start_stops_live(self):
        cb = make_callbacks()
        mock_live = MagicMock()
        cb._live = mock_live
        with patch("roo_agent.cli.app.console"):
            await cb.on_tool_call_start("id1", "read_file", "{}")
        mock_live.stop.assert_called_once()
        assert cb._live is None

    async def test_on_tool_call_end_success_prints_ok(self):
        cb = make_callbacks()
        result = ToolResult.success("file contents")
        with patch("roo_agent.cli.app.console") as mock_console:
            await cb.on_tool_call_end("id1", "read_file", result)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "OK" in output

    async def test_on_tool_call_end_error_prints_error(self):
        cb = make_callbacks()
        result = ToolResult.failure("file not found")
        with patch("roo_agent.cli.app.console") as mock_console:
            await cb.on_tool_call_end("id1", "read_file", result)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Error" in output

    async def test_on_tool_call_end_attempt_completion_renders_panel(self):
        cb = make_callbacks()
        result = ToolResult.success("__attempt_completion__:Task finished!")
        with patch("roo_agent.cli.app.console") as mock_console, \
             patch("roo_agent.cli.app.Panel") as MockPanel:
            await cb.on_tool_call_end("id1", "attempt_completion", result)
        MockPanel.assert_called_once()
        mock_console.print.assert_called()

    async def test_on_tool_call_end_long_output_truncated(self):
        cb = make_callbacks()
        result = ToolResult.success("x" * 1000)
        with patch("roo_agent.cli.app.console"):
            # Should not raise
            await cb.on_tool_call_end("id1", "read_file", result)


# ---------------------------------------------------------------------------
# CLICallbacks — approval
# ---------------------------------------------------------------------------


class TestCLICallbacksApproval:
    async def _invoke_approval(self, response: str) -> str:
        cb = make_callbacks()
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value=response)
            return await cb.on_tool_approval_request("write_file", "id1", {"path": "x"})

    async def test_yes_response(self):
        assert await self._invoke_approval("y") == "y"

    async def test_always_response(self):
        assert await self._invoke_approval("always") == "always"

    async def test_no_response(self):
        assert await self._invoke_approval("n") == "n"

    async def test_long_param_value_does_not_crash(self):
        cb = make_callbacks()
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value="y")
            await cb.on_tool_approval_request("tool", "id1", {"arg": "x" * 300})


# ---------------------------------------------------------------------------
# CLICallbacks — user input
# ---------------------------------------------------------------------------


class TestCLICallbacksUserInput:
    async def test_no_suggestions_returns_stripped(self):
        cb = make_callbacks()
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value="  my answer  ")
            result = await cb.request_user_input("What do you want?", None)
        assert result == "my answer"

    async def test_number_selection_returns_suggestion(self):
        cb = make_callbacks()
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(return_value="2")
            result = await cb.request_user_input("Pick one", ["Option A", "Option B"])
        assert result == "Option B"

    async def test_other_selection_prompts_freetext(self):
        cb = make_callbacks()
        suggestions = ["Option A", "Option B"]
        other_num = str(len(suggestions) + 1)
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=[other_num, "custom answer"]
            )
            result = await cb.request_user_input("Pick one", suggestions)
        assert result == "custom answer"

    async def test_freetext_with_suggestions_treated_as_freetext(self):
        cb = make_callbacks()
        with patch("roo_agent.cli.app.console"), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(
                return_value="I want something else entirely"
            )
            result = await cb.request_user_input("Pick one", ["A", "B"])
        assert result == "I want something else entirely"


# ---------------------------------------------------------------------------
# CLICallbacks — message end
# ---------------------------------------------------------------------------


class TestCLICallbacksMessageEnd:
    async def test_tokens_printed(self):
        cb = make_callbacks()
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        with patch("roo_agent.cli.app.console") as mock_console, \
             patch("roo_agent.cli.app.Live"):
            await cb.on_message_end(usage)
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "100" in output

    async def test_zero_tokens_no_token_line(self):
        cb = make_callbacks()
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        with patch("roo_agent.cli.app.console") as mock_console, \
             patch("roo_agent.cli.app.Live"):
            await cb.on_message_end(usage)
        # No token info when both are 0
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "tokens:" not in output

    async def test_restarts_live_after_end(self):
        cb = make_callbacks()
        usage = TokenUsage(input_tokens=5, output_tokens=3)
        with patch("roo_agent.cli.app.console"), \
             patch("roo_agent.cli.app.Live") as MockLive:
            await cb.on_message_end(usage)
        # Live was created to restart streaming context
        MockLive.assert_called()


# ---------------------------------------------------------------------------
# _handle_history
# ---------------------------------------------------------------------------


class TestHandleHistory:
    async def test_no_args_calls_get_root_tasks(self):
        store = MagicMock()
        task = make_task()
        task.token_usage = TokenUsage()
        store.get_root_tasks = AsyncMock(return_value=[task])
        with patch("roo_agent.cli.app.console"):
            await _handle_history(store, "")
        store.get_root_tasks.assert_awaited_once()

    async def test_no_args_empty_shows_message(self):
        store = MagicMock()
        store.get_root_tasks = AsyncMock(return_value=[])
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_history(store, "")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "No task history" in output

    async def test_with_task_id_found(self):
        store = MagicMock()
        task = make_task()
        store.get_task = AsyncMock(return_value=task)
        store.get_messages = AsyncMock(return_value=[])
        with patch("roo_agent.cli.app.console"):
            await _handle_history(store, "abc123")
        store.get_task.assert_awaited_once_with("abc123")
        store.get_messages.assert_awaited_once_with("abc123")

    async def test_with_task_id_not_found_prints_error(self):
        store = MagicMock()
        store.get_task = AsyncMock(return_value=None)
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_history(store, "bad-id")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "bad-id" in output


# ---------------------------------------------------------------------------
# _handle_export
# ---------------------------------------------------------------------------


class TestHandleExport:
    async def test_no_args_prints_usage(self):
        store = MagicMock()
        settings = MagicMock()
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_export(store, settings, "")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Usage" in output

    async def test_exports_to_file(self, tmp_path):
        store = MagicMock()
        settings = MagicMock()
        settings.data_dir = str(tmp_path)
        export_data = {"id": "abc123", "messages": []}
        with patch("roo_agent.cli.app.export_task", new=AsyncMock(return_value=export_data)), \
             patch("roo_agent.cli.app.console"):
            await _handle_export(store, settings, "abc123")
        files = list((tmp_path / "exports").glob("task-abc123-*.json"))
        assert len(files) == 1

    async def test_task_not_found_prints_error(self):
        store = MagicMock()
        settings = MagicMock()
        with patch("roo_agent.cli.app.export_task", new=AsyncMock(side_effect=ValueError("not found"))), \
             patch("roo_agent.cli.app.console") as mock_console:
            await _handle_export(store, settings, "bad-id")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "not found" in output

    async def test_tree_flag_passed_to_export(self, tmp_path):
        store = MagicMock()
        settings = MagicMock()
        settings.data_dir = str(tmp_path)
        with patch("roo_agent.cli.app.export_task", new=AsyncMock(return_value={"id": "x"})) as mock_exp, \
             patch("roo_agent.cli.app.console"):
            await _handle_export(store, settings, "abc --tree")
        _, kwargs = mock_exp.call_args
        assert kwargs.get("include_children") is True


# ---------------------------------------------------------------------------
# _handle_task
# ---------------------------------------------------------------------------


class TestHandleTask:
    async def test_no_args_prints_task_info(self):
        store = MagicMock()
        task = make_task()
        task.todo_list = []
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_task(store, task, "")
        mock_console.print.assert_called()

    async def test_shows_todo_items(self):
        store = MagicMock()
        task = make_task()
        todo = MagicMock()
        todo.done = True
        todo.text = "Write tests"
        task.todo_list = [todo]
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_task(store, task, "")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Write tests" in output

    async def test_tree_calls_get_children(self):
        store = MagicMock()
        store.get_children = AsyncMock(return_value=[])
        task = make_task()
        with patch("roo_agent.cli.app.console"):
            await _handle_task(store, task, "tree")
        store.get_children.assert_awaited()


# ---------------------------------------------------------------------------
# _handle_model
# ---------------------------------------------------------------------------


def make_agent_with_model(model_id="gpt-4o", provider_name="openai"):
    agent = MagicMock()
    info = MagicMock()
    info.model_id = model_id
    info.provider = provider_name
    info.max_context = 128_000
    info.max_output = 4_096
    info.supports_vision = True
    info.supports_tools = True
    agent.provider.get_model_info.return_value = info
    return agent


class TestHandleModel:
    async def test_no_args_shows_current_model(self):
        settings = MagicMock()
        agent = make_agent_with_model()
        with patch("roo_agent.cli.app.console") as mock_console:
            await _handle_model(settings, agent, "")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "gpt-4o" in output

    async def test_list_shows_catalog(self):
        settings = MagicMock()
        settings.provider.name = "openai"
        agent = make_agent_with_model()
        model_info = MagicMock()
        model_info.model_id = "gpt-4o-mini"
        model_info.max_context = 128_000
        model_info.max_output = 16_000
        model_info.supports_vision = True
        model_info.supports_tools = True
        with patch("roo_agent.cli.app.list_models", return_value=[model_info]), \
             patch("roo_agent.cli.app.console"):
            await _handle_model(settings, agent, "list")

    async def test_list_no_catalog_prints_message(self):
        settings = MagicMock()
        settings.provider.name = "custom"
        agent = make_agent_with_model()
        with patch("roo_agent.cli.app.list_models", return_value=[]), \
             patch("roo_agent.cli.app.console") as mock_console:
            await _handle_model(settings, agent, "list")
        output = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "custom" in output

    async def test_switch_model_success(self):
        settings = MagicMock()
        settings.provider.model = "gpt-4o"
        agent = make_agent_with_model()
        new_provider = MagicMock()
        with patch("roo_agent.cli.app.create_provider", return_value=new_provider), \
             patch("roo_agent.cli.app.console"):
            await _handle_model(settings, agent, "gpt-4o-mini")
        assert agent.provider == new_provider
        assert settings.provider.model == "gpt-4o-mini"

    async def test_switch_model_failure_reverts(self):
        settings = MagicMock()
        settings.provider.model = "gpt-4o"
        agent = make_agent_with_model()
        with patch("roo_agent.cli.app.create_provider", side_effect=ValueError("bad")), \
             patch("roo_agent.cli.app.console"):
            await _handle_model(settings, agent, "nonexistent")
        assert settings.provider.model == "gpt-4o"
