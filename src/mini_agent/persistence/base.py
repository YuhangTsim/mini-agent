"""Base store with shared connection management for both frameworks."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from mini_agent.persistence.schema import SCHEMA_VERSION, UNIFIED_SCHEMA_SQL


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
        await self._db.executescript(UNIFIED_SCHEMA_SQL)
        await self._db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        await self._db.commit()

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
