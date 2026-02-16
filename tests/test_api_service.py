"""Tests for AgentService API layer."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent.api.service import AgentService
from open_agent.bus import EventBus
from open_agent.config import Settings


@pytest.fixture
def event_bus():
    """Create a fresh event bus."""
    bus = EventBus()
    yield bus
    bus.clear()


@pytest.fixture
def real_settings():
    """Create real settings."""
    return Settings()


class TestAgentService:
    """Test AgentService functionality."""
    
    async def test_service_initialization(self, real_settings):
        """Test that service can be initialized."""
        svc = AgentService(settings=real_settings)
        
        assert svc.settings is not None
        assert svc.event_bus is not None
        assert svc._pending_approvals == {}
        assert svc._pending_inputs == {}
    
    async def test_send_message_triggers_processing(self, real_settings):
        """Test that send_message triggers message processing."""
        svc = AgentService(settings=real_settings)
        
        # Mock the app
        svc.app = MagicMock()
        svc.app.initialize = AsyncMock()
        svc.app.shutdown = AsyncMock()
        svc.app.process_message = AsyncMock(return_value="Test response")
        svc.app._session = MagicMock()
        svc.app._session.id = "test-session-123"
        svc.app.bus = svc.event_bus
        
        result = await svc.send_message("Test message", agent_role="explorer")
        
        svc.app.process_message.assert_called_once_with(
            "Test message", agent_role="explorer"
        )
        assert result == "Test response"
    
    async def test_resolve_approval(self, real_settings):
        """Test resolving a pending approval."""
        svc = AgentService(settings=real_settings)
        
        # Create a pending approval
        future = asyncio.get_event_loop().create_future()
        svc._pending_approvals["approval-1"] = future
        
        # Resolve it
        await svc.resolve_approval("approval-1", "approved")
        
        # Future should be resolved
        assert future.done()
        assert await future == "approved"
    
    async def test_resolve_approval_unknown_id(self, real_settings):
        """Test resolving an unknown approval (should not raise)."""
        svc = AgentService(settings=real_settings)
        
        # Should not raise
        await svc.resolve_approval("unknown-id", "approved")
    
    async def test_resolve_input(self, real_settings):
        """Test resolving a pending input."""
        svc = AgentService(settings=real_settings)
        
        future = asyncio.get_event_loop().create_future()
        svc._pending_inputs["input-1"] = future
        
        await svc.resolve_input("input-1", "user response")
        
        assert future.done()
        assert await future == "user response"
    
    async def test_resolve_input_unknown_id(self, real_settings):
        """Test resolving an unknown input (should not raise)."""
        svc = AgentService(settings=real_settings)
        
        await svc.resolve_input("unknown-id", "response")
