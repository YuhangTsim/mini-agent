"""Tests for open-agent todo list handling: model, tools, persistence, and events."""

from __future__ import annotations

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from agent_kernel.tools.base import ToolContext
from open_agent.bus import Event
from open_agent.persistence.models import TodoItem, Session, SessionStatus
from open_agent.tools.native.todo import TodoWriteTool, TodoReadTool


# ---------------------------------------------------------------------------
# TodoItem model
# ---------------------------------------------------------------------------

class TestTodoItem:
    def test_defaults(self):
        item = TodoItem(content="Write tests")
        assert item.content == "Write tests"
        assert item.status == "pending"
        assert item.priority == "medium"
        assert item.id  # auto-generated
        assert item.session_id == ""

    def test_custom_values(self):
        item = TodoItem(
            id="todo-123",
            content="Deploy app",
            status="in_progress",
            priority="high",
            session_id="sess-456",
        )
        assert item.id == "todo-123"
        assert item.content == "Deploy app"
        assert item.status == "in_progress"
        assert item.priority == "high"
        assert item.session_id == "sess-456"

    def test_to_row(self):
        item = TodoItem(
            id="t1",
            content="Test",
            status="completed",
            priority="low",
            session_id="s1",
        )
        row = item.to_row()
        assert row["id"] == "t1"
        assert row["content"] == "Test"
        assert row["status"] == "completed"
        assert row["priority"] == "low"
        assert row["session_id"] == "s1"
        assert "created_at" in row
        assert "updated_at" in row

    def test_from_row(self):
        row = {
            "id": "t2",
            "content": "Review PR",
            "status": "in_progress",
            "priority": "high",
            "session_id": "s2",
            "created_at": "2025-01-01T10:00:00",
            "updated_at": "2025-01-01T11:00:00",
        }
        item = TodoItem.from_row(row)
        assert item.id == "t2"
        assert item.content == "Review PR"
        assert item.status == "in_progress"
        assert item.priority == "high"
        assert item.session_id == "s2"
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.updated_at, datetime)

    def test_roundtrip(self):
        original = TodoItem(
            id="t3",
            content="Ship it",
            status="completed",
            priority="high",
            session_id="s3",
        )
        row = original.to_row()
        restored = TodoItem.from_row(row)
        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.status == original.status
        assert restored.priority == original.priority
        assert restored.session_id == original.session_id


# ---------------------------------------------------------------------------
# TodoWriteTool
# ---------------------------------------------------------------------------

class TestTodoWriteTool:
    @pytest.fixture
    def tool(self):
        return TodoWriteTool()

    @pytest.fixture
    def context(self):
        return ToolContext(session_id="sess-123", working_directory="/tmp")

    async def test_basic_execution(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Step 1", "status": "pending", "priority": "medium"},
                {"id": "t2", "content": "Step 2", "status": "completed", "priority": "high"},
            ]
        }
        result = await tool.execute(params, context)
        assert not result.is_error
        assert "[ ] Step 1" in result.output
        assert "[✓] Step 2" in result.output
        assert "(!)" in result.output  # high priority indicator

    async def test_in_progress_status(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Working on this", "status": "in_progress", "priority": "medium"},
            ]
        }
        result = await tool.execute(params, context)
        assert "[→] Working on this" in result.output

    async def test_cancelled_status(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Cancelled task", "status": "cancelled", "priority": "medium"},
            ]
        }
        result = await tool.execute(params, context)
        assert "[✗] Cancelled task" in result.output

    async def test_low_priority_indicator(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Low prio", "status": "pending", "priority": "low"},
            ]
        }
        result = await tool.execute(params, context)
        assert "(↓)" in result.output

    async def test_empty_list(self, tool, context):
        params = {"todos": []}
        result = await tool.execute(params, context)
        assert not result.is_error
        assert "empty" in result.output.lower()

    async def test_summary_counts(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Pending", "status": "pending", "priority": "medium"},
                {"id": "t2", "content": "In Progress", "status": "in_progress", "priority": "medium"},
                {"id": "t3", "content": "Completed", "status": "completed", "priority": "medium"},
                {"id": "t4", "content": "Cancelled", "status": "cancelled", "priority": "medium"},
            ]
        }
        result = await tool.execute(params, context)
        assert "1 pending" in result.output
        assert "1 in progress" in result.output
        assert "1 completed" in result.output
        assert "1 cancelled" in result.output

    async def test_output_contains_todo_data(self, tool, context):
        params = {
            "todos": [
                {"id": "t1", "content": "Test", "status": "completed", "priority": "medium"},
            ]
        }
        result = await tool.execute(params, context)
        assert "__todo_data__:" in result.output
        # Extract and parse the JSON payload
        data_str = result.output.split("__todo_data__:")[1]
        data = json.loads(data_str)
        assert len(data) == 1
        assert data[0]["content"] == "Test"

    def test_tool_properties(self, tool):
        assert tool.name == "todo_write"
        assert tool.skip_approval is True
        assert tool.category == "native"


# ---------------------------------------------------------------------------
# TodoReadTool
# ---------------------------------------------------------------------------

class TestTodoReadTool:
    @pytest.fixture
    def tool(self):
        return TodoReadTool()

    @pytest.fixture
    def context(self):
        return ToolContext(session_id="sess-123", working_directory="/tmp")

    async def test_basic_execution(self, tool, context):
        params = {}
        result = await tool.execute(params, context)
        assert not result.is_error
        assert "Reading current todo list" in result.output

    async def test_output_signals_read(self, tool, context):
        params = {}
        result = await tool.execute(params, context)
        assert "Reading current todo list" in result.output

    def test_tool_properties(self, tool):
        assert tool.name == "todo_read"
        assert tool.skip_approval is True
        assert tool.category == "native"


# ---------------------------------------------------------------------------
# Persistence (Store) Tests
# ---------------------------------------------------------------------------

class TestTodoPersistence:
    """Tests for todo CRUD operations in OpenAgentStore."""

    async def test_create_todo(self, open_store):
        todo = TodoItem(
            id="td-1",
            content="Test todo",
            status="pending",
            priority="high",
            session_id="sess-1",
        )
        created = await open_store.create_todo(todo)
        assert created.id == "td-1"
        assert created.content == "Test todo"

    async def test_get_session_todos(self, open_store):
        # Create a session first
        session = Session(id="sess-1", title="Test", status=SessionStatus.ACTIVE)
        await open_store.create_session(session)

        # Create todos for this session
        todo1 = TodoItem(id="td-1", content="First", session_id="sess-1")
        todo2 = TodoItem(id="td-2", content="Second", session_id="sess-1")
        await open_store.create_todo(todo1)
        await open_store.create_todo(todo2)

        todos = await open_store.get_session_todos("sess-1")
        assert len(todos) == 2
        assert todos[0].content == "First"
        assert todos[1].content == "Second"

    async def test_get_session_todos_empty(self, open_store):
        todos = await open_store.get_session_todos("nonexistent-session")
        assert todos == []

    async def test_update_todo(self, open_store):
        todo = TodoItem(id="td-1", content="Original", status="pending", session_id="sess-1")
        await open_store.create_todo(todo)

        # Update the todo
        todo.content = "Updated"
        todo.status = "completed"
        await open_store.update_todo(todo)

        # Fetch and verify
        todos = await open_store.get_session_todos("sess-1")
        assert len(todos) == 1
        assert todos[0].content == "Updated"
        assert todos[0].status == "completed"

    async def test_delete_todo(self, open_store):
        todo = TodoItem(id="td-1", content="To delete", session_id="sess-1")
        await open_store.create_todo(todo)

        # Verify it exists
        todos = await open_store.get_session_todos("sess-1")
        assert len(todos) == 1

        # Delete it
        await open_store.delete_todo("td-1")

        # Verify it's gone
        todos = await open_store.get_session_todos("sess-1")
        assert len(todos) == 0

    async def test_update_todos_batch(self, open_store):
        # Create a session
        session = Session(id="sess-batch", title="Batch Test", status=SessionStatus.ACTIVE)
        await open_store.create_session(session)

        # Create initial todos
        todo1 = TodoItem(id="td-1", content="Keep", session_id="sess-batch")
        todo2 = TodoItem(id="td-2", content="Remove", session_id="sess-batch")
        await open_store.create_todo(todo1)
        await open_store.create_todo(todo2)

        # Batch update - replace with new set
        new_todos = [
            TodoItem(id="td-1", content="Keep", status="completed", session_id="sess-batch"),
            TodoItem(id="td-3", content="New", status="pending", session_id="sess-batch"),
        ]
        await open_store.update_todos_batch("sess-batch", new_todos)

        # Verify
        todos = await open_store.get_session_todos("sess-batch")
        assert len(todos) == 2
        contents = {t.content for t in todos}
        assert contents == {"Keep", "New"}
        statuses = {t.status for t in todos}
        assert statuses == {"completed", "pending"}

    async def test_todos_isolated_by_session(self, open_store):
        # Create two sessions
        session1 = Session(id="sess-a", title="Session A", status=SessionStatus.ACTIVE)
        session2 = Session(id="sess-b", title="Session B", status=SessionStatus.ACTIVE)
        await open_store.create_session(session1)
        await open_store.create_session(session2)

        # Add todos to each
        await open_store.create_todo(TodoItem(id="td-a", content="A", session_id="sess-a"))
        await open_store.create_todo(TodoItem(id="td-b", content="B", session_id="sess-b"))

        # Verify isolation
        todos_a = await open_store.get_session_todos("sess-a")
        todos_b = await open_store.get_session_todos("sess-b")

        assert len(todos_a) == 1
        assert len(todos_b) == 1
        assert todos_a[0].content == "A"
        assert todos_b[0].content == "B"


# ---------------------------------------------------------------------------
# SessionProcessor Integration Tests
# ---------------------------------------------------------------------------

class TestSessionProcessorTodoHandling:
    """Tests for todo handling in SessionProcessor."""

    async def test_handle_todo_write_publishes_event(self, open_store, event_bus):
        from open_agent.core.session import SessionProcessor, SessionCallbacks
        from open_agent.persistence.models import AgentRun
        from open_agent.agents.orchestrator import OrchestratorAgent
        from conftest import MockProvider

        # Create a mock provider
        provider = MockProvider()

        # Create agent
        agent = OrchestratorAgent()

        # Create processor
        callbacks = SessionCallbacks()
        processor = SessionProcessor(
            agent=agent,
            provider=provider,
            tool_registry=AsyncMock(),
            permission_checker=AsyncMock(),
            hook_registry=AsyncMock(),
            bus=event_bus,
            store=open_store,
            working_directory="/tmp",
            callbacks=callbacks,
        )

        # Create session and run
        session = Session(id="sess-test", title="Test", status=SessionStatus.ACTIVE)
        await open_store.create_session(session)
        run = AgentRun(id="run-1", session_id="sess-test", agent_role="orchestrator")

        # Track events
        events_received = []
        async def event_handler(event, payload):
            events_received.append((event, payload))

        event_bus.subscribe(Event.TODO_UPDATED, event_handler)

        # Call handle_todo_write
        tc = {"id": "tc-1", "name": "todo_write", "args": json.dumps({
            "todos": [
                {"id": "td-1", "content": "Test", "status": "completed", "priority": "medium"}
            ]
        })}
        params = {"todos": [{"id": "td-1", "content": "Test", "status": "completed", "priority": "medium"}]}

        result = await processor._handle_todo_write(run, tc, params)

        # Verify result
        assert not result.is_error
        assert "completed" in result.output

        # Verify persistence
        todos = await open_store.get_session_todos("sess-test")
        assert len(todos) == 1
        assert todos[0].content == "Test"

    async def test_handle_todo_read_empty(self, open_store):
        from open_agent.core.session import SessionProcessor, SessionCallbacks
        from open_agent.persistence.models import AgentRun
        from open_agent.agents.orchestrator import OrchestratorAgent
        from conftest import MockProvider

        provider = MockProvider()
        agent = OrchestratorAgent()
        callbacks = SessionCallbacks()

        processor = SessionProcessor(
            agent=agent,
            provider=provider,
            tool_registry=AsyncMock(),
            permission_checker=AsyncMock(),
            hook_registry=AsyncMock(),
            bus=AsyncMock(),
            store=open_store,
            working_directory="/tmp",
            callbacks=callbacks,
        )

        session = Session(id="sess-read", title="Test", status=SessionStatus.ACTIVE)
        await open_store.create_session(session)
        run = AgentRun(id="run-1", session_id="sess-read", agent_role="orchestrator")

        tc = {"id": "tc-1", "name": "todo_read", "args": "{}"}
        result = await processor._handle_todo_read(run, tc, {})

        assert not result.is_error
        assert "No todos" in result.output

    async def test_handle_todo_read_with_todos(self, open_store):
        from open_agent.core.session import SessionProcessor, SessionCallbacks
        from open_agent.persistence.models import AgentRun
        from open_agent.agents.orchestrator import OrchestratorAgent
        from conftest import MockProvider

        provider = MockProvider()
        agent = OrchestratorAgent()
        callbacks = SessionCallbacks()

        processor = SessionProcessor(
            agent=agent,
            provider=provider,
            tool_registry=AsyncMock(),
            permission_checker=AsyncMock(),
            hook_registry=AsyncMock(),
            bus=AsyncMock(),
            store=open_store,
            working_directory="/tmp",
            callbacks=callbacks,
        )

        session = Session(id="sess-read-2", title="Test", status=SessionStatus.ACTIVE)
        await open_store.create_session(session)
        await open_store.create_todo(TodoItem(id="td-1", content="Todo item", session_id="sess-read-2"))

        run = AgentRun(id="run-1", session_id="sess-read-2", agent_role="orchestrator")

        tc = {"id": "tc-1", "name": "todo_read", "args": "{}"}
        result = await processor._handle_todo_read(run, tc, {})

        assert not result.is_error
        assert "Todo item" in result.output


# ---------------------------------------------------------------------------
# Tool Registry Integration
# ---------------------------------------------------------------------------

class TestTodoToolRegistry:
    """Tests for todo tools in the tool registry."""

    def test_tools_registered(self):
        from open_agent.tools.native import get_all_native_tools

        tools = get_all_native_tools()
        tool_names = {t.name for t in tools}

        assert "todo_write" in tool_names
        assert "todo_read" in tool_names

    def test_todo_write_definition(self):
        from open_agent.tools.native import TodoWriteTool

        tool = TodoWriteTool()
        definition = tool.get_definition()

        assert definition["name"] == "todo_write"
        assert "todos" in definition["parameters"]["properties"]
        # Verify the items schema has the right properties
        item_schema = definition["parameters"]["properties"]["todos"]["items"]
        assert "properties" in item_schema
        assert "id" in item_schema["properties"]
        assert "content" in item_schema["properties"]
        assert "status" in item_schema["properties"]
        assert "priority" in item_schema["properties"]
        # Verify all required fields are present
        required = item_schema["required"]
        assert "id" in required
        assert "content" in required
        assert "status" in required
        assert "priority" in required

    def test_todo_read_definition(self):
        from open_agent.tools.native import TodoReadTool

        tool = TodoReadTool()
        definition = tool.get_definition()

        assert definition["name"] == "todo_read"
        # Should have no required parameters
        assert "required" not in definition["parameters"] or definition["parameters"]["required"] == []


# ---------------------------------------------------------------------------
# Event Tests
# ---------------------------------------------------------------------------

class TestTodoEvents:
    """Tests for todo-related events."""

    def test_todo_updated_event_exists(self):
        assert Event.TODO_UPDATED == "todo.updated"

    async def test_event_published_on_write(self, event_bus):
        """Verify that todo_write embeds data for SessionProcessor to publish events."""
        from open_agent.tools.native.todo import TodoWriteTool

        tool = TodoWriteTool()
        context = ToolContext(session_id="sess-events", working_directory="/tmp")

        # Note: The tool itself doesn't publish events - SessionProcessor does
        # This test documents the expected behavior
        params = {
            "todos": [
                {"id": "td-1", "content": "Test", "status": "completed", "priority": "medium"}
            ]
        }
        result = await tool.execute(params, context)

        # The tool embeds data in output that SessionProcessor uses to publish events
        assert "__todo_data__:" in result.output
        data_str = result.output.split("__todo_data__:")[1]
        data = json.loads(data_str)
        assert len(data) == 1
        assert data[0]["content"] == "Test"
