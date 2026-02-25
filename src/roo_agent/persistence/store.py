"""SQLite-based persistence store for tasks, messages, and tool calls."""

from __future__ import annotations

from mini_agent.persistence.base import BaseStore
from .models import Task, Message, ToolCall, ConversationSummary


class Store(BaseStore):
    """Async SQLite store for roo-agent persistence.

    Uses the unified schema from mini_agent.persistence with prefixed table names:
    - tasks (unchanged)
    - task_messages (was: messages)
    - task_tool_calls (was: tool_calls)
    """

    # --- Tasks ---

    async def create_task(self, task: Task) -> Task:
        await self._insert("tasks", task.to_row())
        return task

    async def get_task(self, task_id: str) -> Task | None:
        cursor = await self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Task.from_row(dict(row))

    async def update_task(self, task: Task) -> None:
        row = task.to_row()
        sets = ", ".join(f"{k} = ?" for k in row.keys() if k != "id")
        values = [v for k, v in row.items() if k != "id"]
        values.append(task.id)
        await self.db.execute(f"UPDATE tasks SET {sets} WHERE id = ?", values)
        await self.db.commit()

    async def list_tasks(
        self,
        parent_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Task]:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [Task.from_row(dict(r)) for r in rows]

    async def get_root_tasks(self, limit: int = 50) -> list[Task]:
        """Get top-level tasks (no parent)."""
        cursor = await self.db.execute(
            "SELECT * FROM tasks WHERE parent_id IS NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [Task.from_row(dict(r)) for r in rows]

    async def get_children(self, task_id: str) -> list[Task]:
        cursor = await self.db.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [Task.from_row(dict(r)) for r in rows]

    # --- Messages ---

    async def add_message(self, message: Message) -> Message:
        await self._insert("task_messages", message.to_row())
        return message

    async def get_messages(self, task_id: str) -> list[Message]:
        cursor = await self.db.execute(
            "SELECT * FROM task_messages WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [Message.from_row(dict(r)) for r in rows]

    async def get_visible_messages(self, task_id: str) -> list[Message]:
        """Get messages excluding hidden/truncated ones for display."""
        cursor = await self.db.execute(
            """SELECT * FROM task_messages 
               WHERE task_id = ? 
               AND (truncation_parent_id IS NULL OR is_truncation_marker = 1)
               ORDER BY created_at ASC""",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [Message.from_row(dict(r)) for r in rows]

    async def update_message(self, message: Message) -> None:
        """Update an existing message."""
        row = message.to_row()
        sets = ", ".join(f"{k} = ?" for k in row.keys() if k != "id")
        values = [v for k, v in row.items() if k != "id"]
        values.append(message.id)
        await self.db.execute(f"UPDATE task_messages SET {sets} WHERE id = ?", values)
        await self.db.commit()

    # --- Conversation Summaries ---

    async def add_summary(self, summary: ConversationSummary) -> ConversationSummary:
        await self._insert("conversation_summaries", summary.to_row())
        return summary

    async def get_summary(self, task_id: str) -> ConversationSummary | None:
        """Get the most recent summary for a task."""
        cursor = await self.db.execute(
            """SELECT * FROM conversation_summaries 
               WHERE task_id = ? 
               ORDER BY created_at DESC LIMIT 1""",
            (task_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ConversationSummary.from_row(dict(row))

    async def get_summaries(self, task_id: str) -> list[ConversationSummary]:
        """Get all summaries for a task, ordered by creation."""
        cursor = await self.db.execute(
            """SELECT * FROM conversation_summaries 
               WHERE task_id = ? 
               ORDER BY created_at ASC""",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [ConversationSummary.from_row(dict(r)) for r in rows]

    async def delete_summary(self, summary_id: str) -> None:
        """Delete a summary by ID."""
        await self.db.execute("DELETE FROM conversation_summaries WHERE id = ?", (summary_id,))
        await self.db.commit()

    async def delete_message(self, message_id: str) -> None:
        """Delete a message by ID."""
        await self.db.execute("DELETE FROM task_messages WHERE id = ?", (message_id,))
        await self.db.commit()

    # --- Tool Calls ---

    async def add_tool_call(self, tool_call: ToolCall) -> ToolCall:
        await self._insert("task_tool_calls", tool_call.to_row())
        return tool_call

    async def get_tool_calls(self, task_id: str) -> list[ToolCall]:
        cursor = await self.db.execute(
            "SELECT * FROM task_tool_calls WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [ToolCall.from_row(dict(r)) for r in rows]
