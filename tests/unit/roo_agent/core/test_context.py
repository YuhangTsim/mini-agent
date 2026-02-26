"""Tests for roo_agent context management: TokenManager, TruncationStrategy, CondensationStrategy, ContextManager."""

from __future__ import annotations

import pytest

from roo_agent.config.settings import ContextConfig
from roo_agent.core.context import TokenManager, ContextManager
from roo_agent.core.context.strategies import TruncationStrategy, CondensationStrategy
from roo_agent.persistence.models import Message, MessageRole
from roo_agent.persistence.store import Store as RooAgentStore


# Import fixtures from conftest
pytestmark = pytest.mark.asyncio


class TestTokenManager:
    """Tests for TokenManager."""

    def test_default_max_context_from_provider(self, mock_provider):
        """Test default max context tokens comes from provider."""
        tm = TokenManager(provider=mock_provider)
        assert tm.max_context_tokens == 1000  # From MockProvider.get_model_info()

    def test_custom_max_context(self, mock_provider):
        """Test custom max context tokens can be set."""
        tm = TokenManager(provider=mock_provider, max_context_tokens=500)
        assert tm.max_context_tokens == 500

    async def test_count_message_tokens(self, mock_provider):
        """Test counting tokens for a single message."""
        tm = TokenManager(provider=mock_provider)
        msg = Message(
            task_id="task-1",
            role=MessageRole.USER,
            content="Hello world",
        )
        # "user: Hello world" = 3 words
        tokens = await tm.count_message_tokens(msg)
        assert tokens == 3

    async def test_count_messages_tokens(self, mock_provider):
        """Test counting tokens for multiple messages."""
        tm = TokenManager(provider=mock_provider)
        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content="Hello"),
            Message(task_id="task-1", role=MessageRole.ASSISTANT, content="Hi there"),
            Message(task_id="task-1", role=MessageRole.USER, content="How are you?"),
        ]
        tokens = await tm.count_messages_tokens(messages)
        # "user: Hello" (2) + "assistant: Hi there" (3) + "user: How are you?" (4) = 9
        assert tokens == 9

    async def test_get_available_tokens(self, mock_provider):
        """Test available tokens calculation."""
        tm = TokenManager(provider=mock_provider)
        system_prompt = "You are a helpful assistant"  # 5 words
        available = await tm.get_available_tokens(system_prompt)
        assert available == 995  # 1000 - 5

    async def test_needs_truncation_false(self, mock_provider):
        """Test truncation not needed when under threshold."""
        tm = TokenManager(provider=mock_provider)
        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content="Short message"),
        ]
        # Under 90% threshold
        needs = await tm.needs_truncation(messages, "short system", threshold=0.9)
        assert needs is False

    async def test_needs_truncation_true(self, mock_provider):
        """Test truncation needed when over threshold."""
        tm = TokenManager(provider=mock_provider, max_context_tokens=10)
        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content="word " * 5),
        ]
        # This would exceed threshold with system prompt
        needs = await tm.needs_truncation(messages, "system prompt", threshold=0.5)
        assert needs is True

    async def test_get_token_usage(self, mock_provider):
        """Test detailed token usage breakdown."""
        tm = TokenManager(provider=mock_provider)
        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content="Hello world"),
        ]
        usage = await tm.get_token_usage(messages, "System prompt")
        assert usage["system"] == 2  # "System prompt" = 2 words
        assert usage["messages"] == 3  # "user: Hello world" = 3 words
        assert usage["total"] == 5
        assert usage["max"] == 1000
        assert usage["available"] == 995
        assert usage["usage_percent"] == 0.5


class TestTruncationStrategy:
    """Tests for TruncationStrategy."""

    async def test_no_truncate_when_under_limit(self, mock_provider, roo_store):
        """Test no truncation when under keep_recent_messages limit."""
        config = ContextConfig(enabled=True, keep_recent_messages=4)
        tm = TokenManager(provider=mock_provider)
        strategy = TruncationStrategy(config=config, token_manager=tm, store=roo_store)

        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content=f"Message {i}")
            for i in range(3)
        ]

        result = await strategy.truncate(messages, "task-1")
        assert len(result) == 3

    async def test_truncate_creates_marker(self, mock_provider, roo_store):
        """Test truncation creates a marker message."""
        config = ContextConfig(enabled=True, keep_recent_messages=2)
        tm = TokenManager(provider=mock_provider)
        strategy = TruncationStrategy(config=config, token_manager=tm, store=roo_store)

        messages = [
            Message(
                task_id="task-1",
                role=MessageRole.USER,
                content=f"Message {i}",
                id=f"msg-{i}",
            )
            for i in range(5)
        ]

        # Add messages to store first
        for msg in messages:
            await roo_store.add_message(msg)

        result = await strategy.truncate(messages, "task-1")

        # Should have: 1 marker + 2 keep = 3
        assert len(result) == 3

        # First should be the marker
        marker = result[0]
        assert marker.is_truncation_marker is True
        assert "hidden" in marker.content.lower()


class TestCondensationStrategy:
    """Tests for CondensationStrategy."""

    async def test_no_condense_when_under_limit(self, mock_provider, roo_store):
        """Test no condensation when under keep_recent_messages limit."""
        config = ContextConfig(enabled=True, keep_recent_messages=4)
        strategy = CondensationStrategy(config=config, provider=mock_provider, store=roo_store)

        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content=f"Message {i}")
            for i in range(3)
        ]

        result = await strategy.condense(messages, "task-1")
        assert len(result) == 3


class TestContextManager:
    """Tests for ContextManager."""

    async def test_prepare_context_no_management_when_disabled(
        self, mock_provider, roo_store
    ):
        """Test context not managed when disabled."""
        config = ContextConfig(enabled=False)
        manager = ContextManager(config=config, provider=mock_provider, store=roo_store)

        # Add some messages
        for i in range(3):
            msg = Message(
                task_id="task-1",
                role=MessageRole.USER,
                content=f"Message {i}",
            )
            await roo_store.add_message(msg)

        result = await manager.prepare_context("task-1", "system prompt")
        assert len(result) == 3

    async def test_prepare_context_with_truncation(
        self, mock_provider, roo_store
    ):
        """Test context truncation when enabled."""
        config = ContextConfig(
            enabled=True,
            strategy="truncate",
            keep_recent_messages=2,
            truncation_threshold=0.1,  # Very low to trigger truncation
        )
        manager = ContextManager(config=config, provider=mock_provider, store=roo_store)

        # Add messages
        for i in range(5):
            msg = Message(
                task_id="task-2",
                role=MessageRole.USER,
                content=f"Message {i}",
            )
            await roo_store.add_message(msg)

        result = await manager.prepare_context("task-2", "system")
        # Should have truncation marker + 2 kept messages
        assert len(result) >= 2

    async def test_messages_to_dict(self, mock_provider, roo_store):
        """Test converting messages to dict format."""
        config = ContextConfig(enabled=False)
        manager = ContextManager(config=config, provider=mock_provider, store=roo_store)

        messages = [
            Message(task_id="task-1", role=MessageRole.USER, content="Hello"),
            Message(task_id="task-1", role=MessageRole.ASSISTANT, content="Hi"),
        ]

        result = manager._messages_to_dict(messages)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi"}


# Fixtures
@pytest.fixture
def mock_provider():
    """Create a mock provider for testing."""
    from tests.helpers.mock_provider import MockProvider

    return MockProvider()


@pytest.fixture
async def roo_store(tmp_path):
    """Create a roo_agent store for testing."""
    store = RooAgentStore(str(tmp_path / "test.db"))
    await store.initialize()
    yield store
    await store.close()
