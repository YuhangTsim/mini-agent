"""Tests for context management (pruning and compaction)."""

from __future__ import annotations

import pytest

from open_agent.config.settings import CompactionSettings
from open_agent.core.context.pruning import PruningResult, PruningStrategy
from open_agent.persistence.models import (
    Message,
    MessagePart,
)


class TestMessageModel:
    """Test Message model with compaction fields."""

    def test_message_with_compaction_fields(self):
        """Test creating a message with compaction fields."""
        msg = Message(
            content="Test content",
            is_compaction=True,
            summary="This is a summary",
        )
        
        assert msg.is_compaction is True
        assert msg.summary == "This is a summary"
    
    def test_message_to_row_with_compaction(self):
        """Test Message.to_row() includes compaction fields."""
        msg = Message(
            content="Test",
            is_compaction=True,
            summary="Summary",
        )
        row = msg.to_row()
        
        assert row["is_compaction"] == 1
        assert row["summary"] == "Summary"
    
    def test_message_from_row_with_compaction(self):
        """Test Message.from_row() includes compaction fields."""
        row = {
            "id": "msg-1",
            "agent_run_id": "run-1",
            "role": "user",
            "content": "Test",
            "token_count": 10,
            "is_compaction": 1,
            "summary": "Summary text",
            "created_at": "2024-01-01T00:00:00",
        }
        
        msg = Message.from_row(row)
        
        assert msg.is_compaction is True
        assert msg.summary == "Summary text"


class TestMessagePartModel:
    """Test MessagePart model."""

    def test_message_part_creation(self):
        """Test creating a message part."""
        part = MessagePart(
            message_id="msg-1",
            part_type="tool",
            content="Tool output",
            tool_name="read_file",
            tool_state={"status": "success"},
        )
        
        assert part.message_id == "msg-1"
        assert part.part_type == "tool"
        assert part.tool_name == "read_file"
        assert part.tool_state["status"] == "success"
    
    def test_message_part_to_row(self):
        """Test MessagePart.to_row()."""
        part = MessagePart(
            message_id="msg-1",
            part_type="tool",
            content="Output",
            tool_name="search",
            tool_state={"status": "success", "count": 5},
        )
        
        row = part.to_row()
        
        assert row["message_id"] == "msg-1"
        assert row["part_type"] == "tool"
        assert row["tool_name"] == "search"
        assert '"status"' in row["tool_state"]
    
    def test_message_part_from_row(self):
        """Test MessagePart.from_row()."""
        row = {
            "id": "part-1",
            "message_id": "msg-1",
            "part_type": "text",
            "content": "Hello world",
            "tool_name": None,
            "tool_state": "{}",
            "compacted_at": None,
            "created_at": "2024-01-01T00:00:00",
        }
        
        part = MessagePart.from_row(row)
        
        assert part.id == "part-1"
        assert part.part_type == "text"
        assert part.content == "Hello world"
        assert part.compacted_at is None


class TestCompactionSettings:
    """Test CompactionSettings model."""

    def test_default_settings(self):
        """Test default compaction settings."""
        settings = CompactionSettings()
        
        assert settings.auto is True
        assert settings.auto_prune is True
        assert settings.prune_minimum == 20000
        assert settings.prune_protect == 40000
        assert settings.model == "gpt-4o-mini"
    
    def test_custom_settings(self):
        """Test custom compaction settings."""
        settings = CompactionSettings(
            auto=False,
            auto_prune=False,
            prune_minimum=10000,
            prune_protect=20000,
            model="gpt-4o",
        )
        
        assert settings.auto is False
        assert settings.auto_prune is False
        assert settings.prune_minimum == 10000
        assert settings.prune_protect == 20000
        assert settings.model == "gpt-4o"


class TestPruningResult:
    """Test PruningResult dataclass."""

    def test_pruning_result_creation(self):
        """Test creating a PruningResult."""
        result = PruningResult(
            tokens_pruned=5000,
            tool_calls_pruned=10,
            tools_affected=["read_file", "search_files"],
        )
        
        assert result.tokens_pruned == 5000
        assert result.tool_calls_pruned == 10
        assert len(result.tools_affected) == 2


@pytest.mark.asyncio
class TestPruningStrategy:
    """Test PruningStrategy with a mock store."""

    async def test_pruning_strategy_init(self):
        """Test PruningStrategy initialization."""
        # Mock store - we'll test actual pruning with integration tests
        strategy = PruningStrategy(store=None, protect_tokens=30000)
        
        assert strategy.protect_tokens == 30000
        assert strategy.PRUNE_MINIMUM == 20000
        assert strategy.PRUNE_PROTECT == 40000
