"""SQLite-based persistence store for sessions, agent runs, messages, and tool calls."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from open_agent.persistence.models import AgentRun, Message, Session, ToolCall

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'active',
    title TEXT,
    working_directory TEXT,
    metadata TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    parent_run_id TEXT REFERENCES agent_runs(id),
    agent_role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    description TEXT,
    result TEXT,
    is_background INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_session ON agent_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent ON agent_runs(parent_run_id);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    agent_run_id TEXT NOT NULL REFERENCES agent_runs(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_run ON messages(agent_run_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    agent_run_id TEXT NOT NULL REFERENCES agent_runs(id),
    message_id TEXT REFERENCES messages(id),
    tool_name TEXT NOT NULL,
    parameters TEXT,
    result TEXT,
    status TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(agent_run_id);
"""


class Store:
    """Async SQLite store for persistence."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
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

    # --- Helper ---

    async def _insert(self, table: str, row: dict) -> None:
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        await self.db.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        await self.db.commit()

    # --- Sessions ---

    async def create_session(self, session: Session) -> Session:
        await self._insert("sessions", session.to_row())
        return session

    async def get_session(self, session_id: str) -> Session | None:
        cursor = await self.db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return Session.from_row(dict(row)) if row else None

    async def update_session(self, session: Session) -> None:
        row = session.to_row()
        sets = ", ".join(f"{k} = ?" for k in row if k != "id")
        values = [v for k, v in row.items() if k != "id"]
        values.append(session.id)
        await self.db.execute(f"UPDATE sessions SET {sets} WHERE id = ?", values)
        await self.db.commit()

    async def list_sessions(self, limit: int = 50) -> list[Session]:
        cursor = await self.db.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [Session.from_row(dict(r)) for r in rows]

    # --- Agent Runs ---

    async def create_agent_run(self, run: AgentRun) -> AgentRun:
        await self._insert("agent_runs", run.to_row())
        return run

    async def get_agent_run(self, run_id: str) -> AgentRun | None:
        cursor = await self.db.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        return AgentRun.from_row(dict(row)) if row else None

    async def update_agent_run(self, run: AgentRun) -> None:
        row = run.to_row()
        sets = ", ".join(f"{k} = ?" for k in row if k != "id")
        values = [v for k, v in row.items() if k != "id"]
        values.append(run.id)
        await self.db.execute(f"UPDATE agent_runs SET {sets} WHERE id = ?", values)
        await self.db.commit()

    async def get_session_runs(self, session_id: str) -> list[AgentRun]:
        cursor = await self.db.execute(
            "SELECT * FROM agent_runs WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [AgentRun.from_row(dict(r)) for r in rows]

    async def get_child_runs(self, parent_run_id: str) -> list[AgentRun]:
        cursor = await self.db.execute(
            "SELECT * FROM agent_runs WHERE parent_run_id = ? ORDER BY created_at ASC",
            (parent_run_id,),
        )
        rows = await cursor.fetchall()
        return [AgentRun.from_row(dict(r)) for r in rows]

    async def get_background_runs(self, session_id: str) -> list[AgentRun]:
        cursor = await self.db.execute(
            "SELECT * FROM agent_runs WHERE session_id = ? AND is_background = 1 ORDER BY created_at DESC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [AgentRun.from_row(dict(r)) for r in rows]

    # --- Messages ---

    async def add_message(self, message: Message) -> Message:
        await self._insert("messages", message.to_row())
        return message

    async def get_messages(self, agent_run_id: str) -> list[Message]:
        cursor = await self.db.execute(
            "SELECT * FROM messages WHERE agent_run_id = ? ORDER BY created_at ASC",
            (agent_run_id,),
        )
        rows = await cursor.fetchall()
        return [Message.from_row(dict(r)) for r in rows]

    # --- Tool Calls ---

    async def add_tool_call(self, tool_call: ToolCall) -> ToolCall:
        await self._insert("tool_calls", tool_call.to_row())
        return tool_call

    async def get_tool_calls(self, agent_run_id: str) -> list[ToolCall]:
        cursor = await self.db.execute(
            "SELECT * FROM tool_calls WHERE agent_run_id = ? ORDER BY created_at ASC",
            (agent_run_id,),
        )
        rows = await cursor.fetchall()
        return [ToolCall.from_row(dict(r)) for r in rows]
