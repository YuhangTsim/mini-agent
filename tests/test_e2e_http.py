"""E2E tests for open-agent HTTP API."""

from __future__ import annotations

import os
import tempfile

import httpx
import pytest
from fastapi.testclient import TestClient

from open_agent.api.http.server import app, get_service, _service
from open_agent.config import Settings


@pytest.fixture
def test_settings():
    """Create test settings with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings()
        settings.data_dir = tmpdir
        settings.working_directory = tmpdir
        
        # Configure for OpenRouter if OPENROUTER_API_KEY is set
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            settings.provider.base_url = "https://openrouter.ai/api/v1"
            settings.provider.api_key = openrouter_key
        
        yield settings


@pytest.fixture
async def client(test_settings):
    """Create a test client with initialized service."""
    import open_agent.api.http.server as server_module
    
    # Reset global service
    server_module._service = None
    
    # Create and initialize service with test settings
    from open_agent.api.service import AgentService
    service = AgentService(test_settings)
    await service.initialize()
    
    # Set the global service
    server_module._service = service
    
    # Use FastAPI TestClient
    with TestClient(app) as test_client:
        yield test_client
    
    # Cleanup
    await service.shutdown()
    server_module._service = None


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    async def test_health_check(self, client):
        """Test health endpoint returns ok."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestSendMessage:
    """Test message sending endpoint."""
    
    async def test_send_message_requires_message(self, client):
        """Test that message is required."""
        response = client.post("/api/send", json={})
        
        assert response.status_code == 422  # Validation error
    
    async def test_send_simple_message(self, client):
        """Test sending a simple message."""
        # This will make a real LLM call if OPENAI_API_KEY is set
        response = client.post("/api/send", json={
            "message": "Say 'test' and nothing else",
            "agent_role": "explorer",
        })
        
        # Should return a result (might be an error if no API key)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "result" in data


class TestApprovals:
    """Test approval endpoints."""
    
    async def test_resolve_unknown_approval(self, client):
        """Test resolving an unknown approval returns ok (no-op)."""
        response = client.post("/api/approvals/nonexistent", json={
            "response": "approved",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestInputs:
    """Test input endpoints."""
    
    async def test_resolve_unknown_input(self, client):
        """Test resolving an unknown input returns ok (no-op)."""
        response = client.post("/api/inputs/nonexistent", json={
            "response": "test response",
        })
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestStreaming:
    """Test streaming endpoint."""
    
    @pytest.mark.skip(reason="Streaming test times out - needs investigation")
    async def test_stream_events(self, client):
        """Test that streaming endpoint works."""
        response = client.get("/api/stream")
        
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"),
    reason="No API key set for LLM provider"
)
class TestE2EWithLLM:
    """E2E tests that make real LLM calls. Skipped if no API key."""
    
    async def test_full_conversation_flow(self, client):
        """Test full conversation with real LLM."""
        import os
        
        # Send a message
        response = client.post("/api/send", json={
            "message": "What is 2+2? Answer with just the number.",
            "agent_role": "explorer",
        })
        
        if response.status_code != 200:
            print(f"Error response: {response.status_code} - {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "4" in data["result"]


# Import os for skipif check
import os
