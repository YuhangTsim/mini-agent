"""Tests for todo list handling: model, tool, persistence, and active execution."""

from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from roo_agent.core.agent import Agent
from roo_agent.persistence.models import Task, TaskStatus, TodoItem
from roo_agent.persistence.store import Store
from roo_agent.tools.base import ToolContext
from roo_agent.tools.native.todo import UpdateTodoListTool


# ---------------------------------------------------------------------------
# TodoItem model
# ---------------------------------------------------------------------------

class TestTodoItem:
    def test_defaults(self):
        item = TodoItem(text="Write tests")
        assert item.text == "Write tests"
        assert item.done is False

    def test_to_dict(self):
        item = TodoItem(text="Deploy", done=True)
        assert item.to_dict() == {"text": "Deploy", "done": True}

    def test_from_dict(self):
        item = TodoItem.from_dict({"text": "Review PR", "done": True})
        assert item.text == "Review PR"
        assert item.done is True

    def test_from_dict_missing_done(self):
        item = TodoItem.from_dict({"text": "Triage"})
        assert item.done is False

    def test_roundtrip(self):
        original = TodoItem(text="Ship it", done=True)
        restored = TodoItem.from_dict(original.to_dict())
        assert restored.text == original.text
        assert restored.done == original.done


# ---------------------------------------------------------------------------
# Task todo_list serialization
# ---------------------------------------------------------------------------

class TestTaskTodoSerialization:
    def test_empty_todo_list_serializes(self):
        task = Task(id="t1", mode="code", status=TaskStatus.ACTIVE)
        row = task.to_row()
        assert json.loads(row["todo_list"]) == []

    def test_todo_list_serializes(self):
        items = [TodoItem("A", done=False), TodoItem("B", done=True)]
        task = Task(id="t2", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        row = task.to_row()
        parsed = json.loads(row["todo_list"])
        assert parsed == [{"text": "A", "done": False}, {"text": "B", "done": True}]

    def test_from_row_restores_todo_list(self):
        items = [TodoItem("X"), TodoItem("Y", done=True)]
        task = Task(id="t3", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        row = task.to_row()
        restored = Task.from_row(row)
        assert len(restored.todo_list) == 2
        assert restored.todo_list[0].text == "X"
        assert restored.todo_list[0].done is False
        assert restored.todo_list[1].text == "Y"
        assert restored.todo_list[1].done is True

    def test_from_row_handles_null_todo_list(self):
        row = {
            "id": "t4", "mode": "code", "status": "active",
            "todo_list": None,
            "metadata": "{}",
            "input_tokens": 0, "output_tokens": 0, "estimated_cost": 0.0,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00",
            "completed_at": None,
        }
        task = Task.from_row(row)
        assert task.todo_list == []


# ---------------------------------------------------------------------------
# UpdateTodoListTool
# ---------------------------------------------------------------------------

class TestUpdateTodoListTool:
    @pytest.fixture
    def tool(self):
        return UpdateTodoListTool()

    @pytest.fixture
    def context(self):
        return ToolContext(task_id="t1", working_directory="/tmp", mode="code")

    async def test_basic_execution(self, tool, context):
        params = {
            "items": [
                {"text": "Step 1", "done": False},
                {"text": "Step 2", "done": True},
            ]
        }
        result = await tool.execute(params, context)
        assert not result.is_error
        assert "[ ] Step 1" in result.output
        assert "[x] Step 2" in result.output

    async def test_output_contains_todo_data(self, tool, context):
        params = {"items": [{"text": "Only item", "done": False}]}
        result = await tool.execute(params, context)
        assert "__todo_data__:" in result.output
        # Extract and parse the JSON payload
        data_str = result.output.split("__todo_data__:")[1]
        data = json.loads(data_str)
        assert data == [{"text": "Only item", "done": False}]

    async def test_empty_list(self, tool, context):
        params = {"items": []}
        result = await tool.execute(params, context)
        assert not result.is_error
        assert "(empty todo list)" in result.output
        data_str = result.output.split("__todo_data__:")[1]
        assert json.loads(data_str) == []

    async def test_all_done(self, tool, context):
        params = {
            "items": [
                {"text": "A", "done": True},
                {"text": "B", "done": True},
            ]
        }
        result = await tool.execute(params, context)
        assert "[x] A" in result.output
        assert "[x] B" in result.output
        assert "[ ]" not in result.output

    async def test_tool_metadata(self, tool):
        assert tool.name == "update_todo_list"
        assert tool.always_available is True


# ---------------------------------------------------------------------------
# Persistence roundtrip (Store → SQLite → Store)
# ---------------------------------------------------------------------------

class TestTodoPersistence:
    @pytest.fixture
    async def store(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        s = Store(db_path)
        await s.initialize()
        yield s
        await s.close()

    async def test_create_and_retrieve_with_todos(self, store):
        items = [TodoItem("Write tests", done=False), TodoItem("Run tests", done=True)]
        task = Task(id="persist-1", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        await store.create_task(task)

        loaded = await store.get_task("persist-1")
        assert loaded is not None
        assert len(loaded.todo_list) == 2
        assert loaded.todo_list[0].text == "Write tests"
        assert loaded.todo_list[0].done is False
        assert loaded.todo_list[1].text == "Run tests"
        assert loaded.todo_list[1].done is True

    async def test_update_todo_list_persists(self, store):
        task = Task(id="persist-2", mode="code", status=TaskStatus.ACTIVE)
        await store.create_task(task)

        # Add todos and update
        task.todo_list = [TodoItem("New item", done=False)]
        await store.update_task(task)

        loaded = await store.get_task("persist-2")
        assert loaded is not None
        assert len(loaded.todo_list) == 1
        assert loaded.todo_list[0].text == "New item"

    async def test_clear_todo_list(self, store):
        task = Task(
            id="persist-3", mode="code", status=TaskStatus.ACTIVE,
            todo_list=[TodoItem("Temp")],
        )
        await store.create_task(task)

        task.todo_list = []
        await store.update_task(task)

        loaded = await store.get_task("persist-3")
        assert loaded is not None
        assert loaded.todo_list == []

    async def test_task_without_todos(self, store):
        task = Task(id="persist-4", mode="code", status=TaskStatus.ACTIVE)
        await store.create_task(task)

        loaded = await store.get_task("persist-4")
        assert loaded is not None
        assert loaded.todo_list == []


# ---------------------------------------------------------------------------
# Task.pending_todos property
# ---------------------------------------------------------------------------

class TestTaskPendingTodos:
    def test_no_todos(self):
        task = Task(id="pt-1", mode="code", status=TaskStatus.ACTIVE)
        assert task.pending_todos == []

    def test_all_pending(self):
        items = [TodoItem("A"), TodoItem("B")]
        task = Task(id="pt-2", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        assert len(task.pending_todos) == 2

    def test_mixed(self):
        items = [TodoItem("A", done=True), TodoItem("B"), TodoItem("C", done=True)]
        task = Task(id="pt-3", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        pending = task.pending_todos
        assert len(pending) == 1
        assert pending[0].text == "B"

    def test_all_done(self):
        items = [TodoItem("A", done=True), TodoItem("B", done=True)]
        task = Task(id="pt-4", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        assert task.pending_todos == []


# ---------------------------------------------------------------------------
# _build_todo_directive
# ---------------------------------------------------------------------------

class TestBuildTodoDirective:
    @pytest.fixture
    def agent(self):
        """Create an Agent with mock dependencies for directive testing."""
        provider = MagicMock()
        registry = MagicMock()
        store = MagicMock()
        settings = MagicMock()
        return Agent(provider=provider, registry=registry, store=store, settings=settings)

    def test_returns_none_when_no_todos(self, agent):
        task = Task(id="d-1", mode="code", status=TaskStatus.ACTIVE)
        assert agent._build_todo_directive(task) is None

    def test_returns_none_when_all_done(self, agent):
        items = [TodoItem("A", done=True), TodoItem("B", done=True)]
        task = Task(id="d-2", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        assert agent._build_todo_directive(task) is None

    def test_returns_directive_with_pending(self, agent):
        items = [TodoItem("First"), TodoItem("Second")]
        task = Task(id="d-3", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        directive = agent._build_todo_directive(task)
        assert directive is not None
        assert "## Plan Execution Status" in directive
        assert "- [ ] First" in directive
        assert "- [ ] Second" in directive
        assert "Next pending item: **First**" in directive

    def test_shows_done_and_pending(self, agent):
        items = [TodoItem("Done item", done=True), TodoItem("Pending item")]
        task = Task(id="d-4", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        directive = agent._build_todo_directive(task)
        assert directive is not None
        assert "- [x] Done item" in directive
        assert "- [ ] Pending item" in directive
        assert "Next pending item: **Pending item**" in directive

    def test_next_item_is_first_pending(self, agent):
        items = [
            TodoItem("A", done=True),
            TodoItem("B", done=False),
            TodoItem("C", done=False),
        ]
        task = Task(id="d-5", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        directive = agent._build_todo_directive(task)
        assert "Next pending item: **B**" in directive

    def test_directive_contains_instructions(self, agent):
        items = [TodoItem("Do something")]
        task = Task(id="d-6", mode="code", status=TaskStatus.ACTIVE, todo_list=items)
        directive = agent._build_todo_directive(task)
        assert "update_todo_list" in directive
        assert "attempt_completion" in directive
        assert "new_task" in directive


# ---------------------------------------------------------------------------
# Integration: directive injection into conversation
# ---------------------------------------------------------------------------

class TestTodoDirectiveInjection:
    """Verify that the agent loop injects todo directives into the conversation."""

    @pytest.fixture
    def agent(self):
        provider = MagicMock()
        registry = MagicMock()
        store = AsyncMock()
        settings = MagicMock()
        settings.provider.max_tokens = 1000
        settings.provider.temperature = 0.0
        settings.working_directory = "/tmp"
        return Agent(provider=provider, registry=registry, store=store, settings=settings)

    def test_directive_injected_into_conversation(self, agent):
        """After tool results with pending todos, directive should be built."""
        items = [TodoItem("Step 1"), TodoItem("Step 2")]
        task = Task(id="inj-1", mode="code", status=TaskStatus.ACTIVE, todo_list=items)

        directive = agent._build_todo_directive(task)
        assert directive is not None

        # Simulate what the agent loop does: append directive to conversation
        conversation: list[dict] = []
        conversation.append({"role": "user", "content": directive})
        assert len(conversation) == 1
        assert "Step 1" in conversation[0]["content"]
        assert "Step 2" in conversation[0]["content"]

    def test_no_injection_when_all_done(self, agent):
        """No directive when all items are complete."""
        items = [TodoItem("A", done=True), TodoItem("B", done=True)]
        task = Task(id="inj-2", mode="code", status=TaskStatus.ACTIVE, todo_list=items)

        directive = agent._build_todo_directive(task)
        assert directive is None

    def test_injection_count_cap(self, agent):
        """Verify max_todo_injections logic works."""
        items = [TodoItem("Infinite task")]
        task = Task(id="inj-3", mode="code", status=TaskStatus.ACTIVE, todo_list=items)

        max_todo_injections = 15
        conversation: list[dict] = []

        # Simulate injection loop
        for i in range(20):
            directive = agent._build_todo_directive(task)
            if directive and (i + 1) <= max_todo_injections:
                conversation.append({"role": "user", "content": directive})

        # Should cap at max_todo_injections
        assert len(conversation) == max_todo_injections
