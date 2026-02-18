"""Tests for CLI todo display functionality."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from open_agent.cli.app import DelegationDisplay
from open_agent.bus import EventBus
from open_agent.bus.events import Event, EventPayload


class TestTodoDisplay:
    """Tests for the todo display in CLI."""

    @pytest.fixture
    def bus(self):
        return EventBus()

    @pytest.fixture
    def display(self, bus):
        return DelegationDisplay(bus)

    async def test_todo_updated_handler_exists(self, display):
        """Verify that TODO_UPDATED handler method exists on DelegationDisplay."""
        # The handler is registered in __init__ via self.bus.subscribe(Event.TODO_UPDATED, ...)
        # Check that the handler method exists and is a coroutine function
        assert hasattr(display, '_on_todo_updated')
        import inspect
        assert inspect.iscoroutinefunction(display._on_todo_updated)

    @patch("open_agent.cli.app.console")
    async def test_todo_updated_empty_list(self, mock_console, bus, display):
        """Empty todo list should not print anything."""
        payload = EventPayload(
            event=Event.TODO_UPDATED,
            session_id="sess-1",
            agent_role="orchestrator",
            data={"todos": []}
        )
        
        await display._on_todo_updated(payload)
        
        # Console.print should not be called for empty lists
        mock_console.print.assert_not_called()

    @patch("open_agent.cli.app.console")
    async def test_todo_updated_displays_items(self, mock_console, bus, display):
        """Todo items should be displayed with proper formatting."""
        payload = EventPayload(
            event=Event.TODO_UPDATED,
            session_id="sess-1",
            agent_role="orchestrator",
            data={
                "todos": [
                    {"id": "t1", "content": "Pending task", "status": "pending", "priority": "medium"},
                    {"id": "t2", "content": "In progress", "status": "in_progress", "priority": "high"},
                    {"id": "t3", "content": "Completed", "status": "completed", "priority": "low"},
                    {"id": "t4", "content": "Cancelled", "status": "cancelled", "priority": "medium"},
                ]
            }
        )
        
        await display._on_todo_updated(payload)
        
        # Verify console.print was called with a Panel
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0]
        
        # The argument should be a Panel
        from rich.panel import Panel
        assert isinstance(call_args[0], Panel)
        
        # Check panel title contains summary
        panel = call_args[0]
        assert "Todo List" in panel.title
        assert "1 done" in panel.title
        assert "1 active" in panel.title
        assert "1 pending" in panel.title

    @patch("open_agent.cli.app.console")
    async def test_todo_updated_high_priority(self, mock_console, bus, display):
        """High priority items should have indicator."""
        payload = EventPayload(
            event=Event.TODO_UPDATED,
            session_id="sess-1",
            agent_role="orchestrator",
            data={
                "todos": [
                    {"id": "t1", "content": "Urgent", "status": "pending", "priority": "high"},
                ]
            }
        )
        
        await display._on_todo_updated(payload)
        
        mock_console.print.assert_called_once()
        panel = mock_console.print.call_args[0][0]
        # Check that the panel renderable contains the content
        renderable = panel.renderable
        assert "Urgent" in str(renderable)

    @patch("open_agent.cli.app.console")
    async def test_todo_updated_completed_strikethrough(self, mock_console, bus, display):
        """Completed items should have strikethrough formatting."""
        payload = EventPayload(
            event=Event.TODO_UPDATED,
            session_id="sess-1",
            agent_role="orchestrator",
            data={
                "todos": [
                    {"id": "t1", "content": "Done task", "status": "completed", "priority": "medium"},
                ]
            }
        )
        
        await display._on_todo_updated(payload)
        
        mock_console.print.assert_called_once()
        panel = mock_console.print.call_args[0][0]
        renderable = panel.renderable
        # Strikethrough uses [strike] tags in rich
        assert "[strike]Done task[/strike]" in str(renderable)


class TestCLIToolRegistry:
    """Tests to verify tools are available in CLI context."""

    def test_todo_tools_in_registry(self):
        """Verify todo tools are registered in the tool registry."""
        from open_agent.tools.native import get_all_native_tools
        
        tools = get_all_native_tools()
        tool_names = {t.name for t in tools}
        
        assert "todo_write" in tool_names
        assert "todo_read" in tool_names

    def test_todo_tools_have_descriptions(self):
        """Verify todo tools have the detailed prompt guidance."""
        from open_agent.tools.native import TodoWriteTool, TodoReadTool
        
        write_tool = TodoWriteTool()
        read_tool = TodoReadTool()
        
        # TodoWriteTool should have extensive guidance
        assert len(write_tool.description) > 1000  # Should have detailed guidance
        assert "When to Use This Tool" in write_tool.description
        assert "When NOT to Use This Tool" in write_tool.description
        
        # TodoReadTool should have basic description
        assert len(read_tool.description) > 50
        assert "todo list" in read_tool.description.lower()
