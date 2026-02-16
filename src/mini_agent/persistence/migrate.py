"""Legacy DB migration: merge tasks.db and sessions.db into unified agent.db."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


def migrate_legacy_dbs(data_dir: str) -> None:
    """Detect and migrate legacy databases to unified agent.db.

    Copies data from legacy `tasks.db` and `sessions.db` into `agent.db`
    with renamed tables, then renames old files to `.bak`.

    Safe to call multiple times — skips if legacy files are already gone.
    """
    data_path = Path(data_dir)
    agent_db = data_path / "agent.db"
    tasks_db = data_path / "tasks.db"
    sessions_db = data_path / "sessions.db"

    if not tasks_db.exists() and not sessions_db.exists():
        return  # Nothing to migrate

    # Ensure agent.db exists (will be created by BaseStore.initialize() normally)
    dest = sqlite3.connect(str(agent_db))

    try:
        if tasks_db.exists():
            _migrate_roo_tables(dest, str(tasks_db))
            _backup(tasks_db)

        if sessions_db.exists():
            _migrate_open_tables(dest, str(sessions_db))
            _backup(sessions_db)
    finally:
        dest.close()


def _migrate_roo_tables(dest: sqlite3.Connection, source_path: str) -> None:
    """Copy roo-agent data from tasks.db into agent.db with renamed tables."""
    dest.execute(f"ATTACH DATABASE '{source_path}' AS legacy")

    # Check if legacy has the old table names
    tables = {
        row[0]
        for row in dest.execute(
            "SELECT name FROM legacy.sqlite_master WHERE type='table'"
        ).fetchall()
    }

    if "tasks" in tables:
        # tasks table keeps same name
        dest.execute(
            "INSERT OR IGNORE INTO tasks SELECT * FROM legacy.tasks"
        )

    if "messages" in tables:
        # messages -> task_messages
        dest.execute(
            "INSERT OR IGNORE INTO task_messages SELECT * FROM legacy.messages"
        )

    if "tool_calls" in tables:
        # tool_calls -> task_tool_calls
        dest.execute(
            "INSERT OR IGNORE INTO task_tool_calls SELECT * FROM legacy.tool_calls"
        )

    dest.execute("DETACH DATABASE legacy")
    dest.commit()


def _migrate_open_tables(dest: sqlite3.Connection, source_path: str) -> None:
    """Copy open-agent data from sessions.db into agent.db with renamed tables."""
    dest.execute(f"ATTACH DATABASE '{source_path}' AS legacy")

    tables = {
        row[0]
        for row in dest.execute(
            "SELECT name FROM legacy.sqlite_master WHERE type='table'"
        ).fetchall()
    }

    if "sessions" in tables:
        dest.execute(
            "INSERT OR IGNORE INTO sessions SELECT * FROM legacy.sessions"
        )

    if "agent_runs" in tables:
        dest.execute(
            "INSERT OR IGNORE INTO agent_runs SELECT * FROM legacy.agent_runs"
        )

    if "messages" in tables:
        # messages -> run_messages
        dest.execute(
            "INSERT OR IGNORE INTO run_messages SELECT * FROM legacy.messages"
        )

    if "tool_calls" in tables:
        # tool_calls -> run_tool_calls
        dest.execute(
            "INSERT OR IGNORE INTO run_tool_calls SELECT * FROM legacy.tool_calls"
        )

    dest.execute("DETACH DATABASE legacy")
    dest.commit()


def _backup(path: Path) -> None:
    """Rename a file to .bak."""
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.move(str(path), str(bak))
    else:
        path.unlink()
