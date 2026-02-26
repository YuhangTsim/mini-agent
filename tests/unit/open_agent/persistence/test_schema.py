"""Schema sanity checks for the OpenAgent persistence tables."""

from __future__ import annotations


async def test_run_messages_includes_compaction_columns(open_store):
    cursor = await open_store.db.execute("PRAGMA table_info(run_messages)")
    rows = await cursor.fetchall()
    column_names = {row["name"] for row in rows}

    assert "is_compaction" in column_names
    assert "summary" in column_names


async def test_message_parts_table_and_index_exist(open_store):
    cursor = await open_store.db.execute("PRAGMA table_info(message_parts)")
    rows = await cursor.fetchall()
    column_names = {row["name"] for row in rows}

    expected_columns = {
        "id",
        "message_id",
        "part_type",
        "content",
        "tool_name",
        "tool_state",
        "compacted_at",
        "created_at",
    }
    assert expected_columns.issubset(column_names)

    cursor = await open_store.db.execute("PRAGMA index_list('message_parts')")
    indexes = {row["name"] for row in await cursor.fetchall()}
    assert "idx_message_parts_message" in indexes
