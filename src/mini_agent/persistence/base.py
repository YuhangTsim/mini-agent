"""Base store with shared connection management for both frameworks."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from mini_agent.persistence.schema import SCHEMA_VERSION, UNIFIED_SCHEMA_SQL


# Migration scripts for schema upgrades
MIGRATIONS: dict[int, list[str]] = {
    # Version 1 -> 2: Add roo-agent context management columns
    2: [
        "ALTER TABLE task_messages ADD COLUMN truncation_parent_id TEXT",
        "ALTER TABLE task_messages ADD COLUMN is_truncation_marker INTEGER DEFAULT 0",
        "ALTER TABLE task_messages ADD COLUMN is_summary INTEGER DEFAULT 0",
        "ALTER TABLE task_messages ADD COLUMN condense_parent_id TEXT",
    ],
    # Version 2 -> 3: Add compaction fields
    3: [
        "ALTER TABLE run_messages ADD COLUMN is_compaction INTEGER DEFAULT 0",
        "ALTER TABLE run_messages ADD COLUMN summary TEXT",
        """
        CREATE TABLE IF NOT EXISTS message_parts (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL REFERENCES run_messages(id),
            part_type TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_name TEXT,
            tool_state TEXT,
            compacted_at INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_message_parts_message ON message_parts(message_id)",
    ],
    # Version 3 -> 4: Fix missing columns in existing databases
    4: [
        "ALTER TABLE task_messages ADD COLUMN truncation_parent_id TEXT",
        "ALTER TABLE task_messages ADD COLUMN is_truncation_marker INTEGER DEFAULT 0",
        "ALTER TABLE task_messages ADD COLUMN is_summary INTEGER DEFAULT 0",
        "ALTER TABLE task_messages ADD COLUMN condense_parent_id TEXT",
    ],
}


class BaseStore:
    """Async SQLite store with shared connection management and schema setup."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database and ensure unified schema exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        
        # Get current schema version
        current_version = await self._get_schema_version()
        
        if current_version == 0:
            # Fresh install - create full schema
            await self._db.executescript(UNIFIED_SCHEMA_SQL)
            await self._db.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        elif current_version < SCHEMA_VERSION:
            # Run migrations
            await self._run_migrations(current_version, SCHEMA_VERSION)
        
        await self._db.commit()

    async def _get_schema_version(self) -> int:
        """Get the current schema version from the database."""
        try:
            cursor = await self._db.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            return row["version"] if row else 0
        except Exception:
            return 0

    async def _run_migrations(self, from_version: int, to_version: int) -> None:
        """Run migration scripts to upgrade schema."""
        for version in range(from_version + 1, to_version + 1):
            if version in MIGRATIONS:
                for sql in MIGRATIONS[version]:
                    if sql.strip():
                        try:
                            if sql.strip().upper().startswith("CREATE"):
                                # CREATE statements need executescript
                                await self._db.executescript(sql)
                            else:
                                await self._db.execute(sql)
                        except aiosqlite.OperationalError as e:
                            # Ignore "duplicate column name" errors - column may already exist
                            if "duplicate column name" not in str(e):
                                raise
                await self._db.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,),
                )

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Get the active database connection."""
        if self._db is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._db

    async def _insert(self, table: str, row: dict) -> None:
        """Insert a row into the given table."""
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        await self.db.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(row.values()),
        )
        await self.db.commit()
