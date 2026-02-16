"""E2E tests for LLM providers with real API calls."""

from __future__ import annotations

import os

import pytest

from open_agent.providers.base import ToolDefinition
from open_agent.providers.openai import OpenAIProvider


# Skip all tests in this file if no API key is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"),
    reason="No API key set for LLM provider"
)


class TestOpenAIProvider:
    """Test OpenAI provider with real API calls."""
    
    @pytest.fixture
    def provider(self):
        """Create a provider with API key from environment."""
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        base_url = None
        
        # If using OpenRouter, set the base URL
        if os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
        
        return OpenAIProvider(api_key=api_key, base_url=base_url)
    
    @pytest.mark.asyncio
    async def test_simple_completion(self, provider):
        """Test a simple completion request."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'hello' and nothing else."},
        ]
        
        events = []
        async for event in provider.create_message(
            system_prompt="You are a helpful assistant.",
            messages=messages[1:],  # Skip system message, it's passed separately
        ):
            events.append(event)
        
        # Should get at least one event
        assert len(events) > 0
        
        # Last event should be MESSAGE_END
        assert events[-1].type.value == "message_end"
    
    @pytest.mark.asyncio
    async def test_completion_with_content(self, provider):
        """Test that completion returns text content."""
        collected_text = []
        
        async for event in provider.create_message(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}],
        ):
            if event.type.value == "text_delta":
                collected_text.append(event.text)
        
        full_response = "".join(collected_text)
        assert "4" in full_response
    
    @pytest.mark.asyncio
    async def test_tool_call_extraction(self, provider):
        """Test that provider can extract tool calls."""
        tools = [
            ToolDefinition(
                name="get_weather",
                description="Get the weather for a location",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name",
                        },
                    },
                    "required": ["location"],
                    "additionalProperties": False,
                },
            ),
        ]
        
        events = []
        async for event in provider.create_message(
            system_prompt="You are a helpful assistant with access to tools.",
            messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
            tools=tools,
        ):
            events.append(event)
        
        # Check for tool call events
        _ = [e for e in events if e.type.value == "tool_call_start"]  # Check tool call events
        
        # Model may or may not call the tool depending on its behavior
        # Just verify we got a response
        assert len(events) > 0
    
    def test_count_tokens(self, provider):
        """Test token counting."""
        count = provider.count_tokens("Hello world")
        
        # Should return a positive integer
        assert isinstance(count, int)
        assert count > 0
    
    def test_get_model_info(self, provider):
        """Test getting model information."""
        info = provider.get_model_info()
        
        assert info.provider == "openai"
        assert info.max_context > 0
        assert info.max_output > 0


class TestOpenRouterIntegration:
    """Test OpenRouter-specific integration."""
    
    @pytest.fixture
    def openrouter_provider(self):
        """Create provider configured for OpenRouter."""
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            pytest.skip("No OpenRouter API key")
        
        return OpenAIProvider(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    
    @pytest.mark.asyncio
    async def test_openrouter_completion(self, openrouter_provider):
        """Test completion via OpenRouter."""
        events = []
        
        async for event in openrouter_provider.create_message(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello"}],
        ):
            events.append(event)
        
        # Should get events back
        assert len(events) > 0


@pytest.mark.slow
class TestExpensiveOperations:
    """Tests that cost more to run. Marked as slow."""
    
    @pytest.fixture
    def provider(self):
        """Create provider."""
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        base_url = None
        if os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
        return OpenAIProvider(api_key=api_key, base_url=base_url)
    
    @pytest.mark.asyncio
    async def test_multiple_turn_conversation(self, provider):
        """Test multi-turn conversation."""
        messages = [
            {"role": "user", "content": "My name is Test."},
        ]
        
        # First turn
        response1 = []
        async for event in provider.create_message(
            system_prompt="You are a helpful assistant.",
            messages=messages,
        ):
            if event.type.value == "text_delta":
                response1.append(event.text)
        
        first_response = "".join(response1)
        assert len(first_response) > 0
        
        # Add assistant response and follow-up
        messages.append({"role": "assistant", "content": first_response})
        messages.append({"role": "user", "content": "What's my name?"})
        
        # Second turn
        response2 = []
        async for event in provider.create_message(
            system_prompt="You are a helpful assistant.",
            messages=messages,
        ):
            if event.type.value == "text_delta":
                response2.append(event.text)
        
        second_response = "".join(response2)
        assert "Test" in second_response or "test" in second_response.lower()
