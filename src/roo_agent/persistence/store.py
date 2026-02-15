"""SQLite-based persistence store for tasks, messages, and tool calls."""

from __future__ import annotations

import aiosqlite
from pathlib import Path

from .models import Task, Message, ToolCall


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES tasks(id),
    root_id TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    title TEXT,
    description TEXT,
    working_directory TEXT,
    result TEXT,
    todo_list TEXT,
    metadata TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    message_id TEXT REFERENCES messages(id),
    tool_name TEXT NOT NULL,
    parameters TEXT,
    result TEXT,
    status TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_task_id ON tool_calls(task_id);
"""


class Store:
    """Async SQLite store for persistence."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database and ensure schema exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        # Set schema version
        await self._db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._db

    # --- Tasks ---

    async def create_task(self, task: Task) -> Task:
        row = task.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        await self.db.execute(
            f"INSERT INTO tasks ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        await self.db.commit()
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
        row = message.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        await self.db.execute(
            f"INSERT INTO messages ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        await self.db.commit()
        return message

    async def get_messages(self, task_id: str) -> list[Message]:
        cursor = await self.db.execute(
            "SELECT * FROM messages WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [Message.from_row(dict(r)) for r in rows]

    # --- Tool Calls ---

    async def add_tool_call(self, tool_call: ToolCall) -> ToolCall:
        row = tool_call.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        await self.db.execute(
            f"INSERT INTO tool_calls ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        await self.db.commit()
        return tool_call

    async def get_tool_calls(self, task_id: str) -> list[ToolCall]:
        cursor = await self.db.execute(
            "SELECT * FROM tool_calls WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [ToolCall.from_row(dict(r)) for r in rows]
