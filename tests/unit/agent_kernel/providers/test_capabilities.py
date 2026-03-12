"""Tests for provider capability detection.

Tests the following capability scenarios:
1. Vision model detection - checking if model supports vision from PROVIDER_MODELS
2. Reasoning/thinking support detection - checking thinking_budget_tokens availability
3. Tool calling availability - checking if model supports tools
4. Streaming support verification - checking streaming parameter functionality
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_kernel.providers.base import ModelInfo, PROVIDER_MODELS
from agent_kernel.providers.openai import OpenAIProvider
from agent_kernel.providers import registry


def make_provider(
    model: str = "gpt-4o",
    provider_name: str = "openai",
) -> OpenAIProvider:
    """Create an OpenAIProvider with a fake base_url (no API key validation)."""
    return OpenAIProvider(
        api_key="test-key",
        model=model,
        base_url="http://localhost:11434/v1",
        provider_name=provider_name,
    )


class TestVisionModelDetection:
    """Tests for vision model capability detection."""

    def test_vision_models_from_provider_catalog(self):
        """Test that vision models are correctly identified from PROVIDER_MODELS."""
        # Check OpenAI models that should support vision
        openai_models = PROVIDER_MODELS.get("openai", [])
        vision_models = [m for m in openai_models if m.supports_vision]

        # Verify expected vision models
        vision_model_ids = [m.model_id for m in vision_models]
        assert "gpt-4o" in vision_model_ids
        assert "gpt-4o-mini" in vision_model_ids
        assert "gpt-4-turbo" in vision_model_ids

    def test_non_vision_models_from_provider_catalog(self):
        """Test that non-vision models are correctly identified."""
        openai_models = PROVIDER_MODELS.get("openai", [])
        non_vision_models = [m for m in openai_models if not m.supports_vision]

        non_vision_model_ids = [m.model_id for m in non_vision_models]
        assert "gpt-3.5-turbo" in non_vision_model_ids

    def test_openrouter_vision_models(self):
        """Test vision detection for OpenRouter models."""
        openrouter_models = PROVIDER_MODELS.get("openrouter", [])
        vision_models = [m for m in openrouter_models if m.supports_vision]

        vision_model_ids = [m.model_id for m in vision_models]
        assert any("claude" in mid for mid in vision_model_ids)
        assert any("gemini" in mid for mid in vision_model_ids)

    def test_ollama_non_vision_models(self):
        """Test that Ollama models don't support vision in the catalog."""
        ollama_models = PROVIDER_MODELS.get("ollama", [])
        vision_models = [m for m in ollama_models if m.supports_vision]

        # Ollama models in catalog don't support vision
        assert len(vision_models) == 0

    def test_provider_get_model_info_vision(self):
        """Test OpenAIProvider.get_model_info() returns correct vision support."""
        # Test vision model
        provider = make_provider(model="gpt-4o")
        info = provider.get_model_info()
        assert info.supports_vision is True

        # Test non-vision model
        provider = make_provider(model="gpt-3.5-turbo")
        info = provider.get_model_info()
        assert info.supports_vision is False

    def test_vision_detection_for_specific_models(self):
        """Test vision detection for specific model IDs."""
        # Test known vision models
        vision_test_cases = [
            ("gpt-4o", True),
            ("gpt-4o-mini", True),
            ("gpt-4-turbo", True),
        ]

        for model_id, expected in vision_test_cases:
            provider = make_provider(model=model_id)
            info = provider.get_model_info()
            assert info.supports_vision is expected, f"Model {model_id} vision detection failed"

        # Test non-vision models
        non_vision_test_cases = [
            ("gpt-3.5-turbo", False),
            ("gpt-4", False),
        ]

        for model_id, expected in non_vision_test_cases:
            provider = make_provider(model=model_id)
            info = provider.get_model_info()
            assert info.supports_vision is expected, f"Model {model_id} vision detection failed"


class TestReasoningThinkingSupport:
    """Tests for reasoning/thinking capability detection."""

    @pytest.mark.asyncio
    async def test_thinking_budget_parameter_accepted(self):
        """Test that thinking_budget_tokens parameter is accepted by provider."""
        provider = make_provider(model="gpt-4o")

        async def mock_stream():
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta.content = "test"
            choice.delta.reasoning_content = None
            choice.delta.tool_calls = None
            choice.finish_reason = "stop"
            chunk.choices = [choice]
            chunk.usage = MagicMock()
            chunk.usage.prompt_tokens = 10
            chunk.usage.completion_tokens = 5
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            # This should not raise an error
            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                thinking_budget_tokens=5000,
            ):
                events.append(event)

            # Verify call was made with thinking parameter
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert "thinking" in call_kwargs
            assert call_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 5000}

    @pytest.mark.asyncio
    async def test_thinking_parameter_none_disables(self):
        """Test that thinking_budget_tokens=None disables extended thinking."""
        provider = make_provider(model="gpt-4o")

        async def mock_stream():
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta.content = "test"
            choice.delta.reasoning_content = None
            choice.delta.tool_calls = None
            choice.finish_reason = "stop"
            chunk.choices = [choice]
            chunk.usage = MagicMock()
            chunk.usage.prompt_tokens = 10
            chunk.usage.completion_tokens = 5
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            async for _ in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                thinking_budget_tokens=None,
            ):
                pass

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            # When None, thinking should not be in kwargs
            assert "thinking" not in call_kwargs

    @pytest.mark.asyncio
    async def test_reasoning_content_parsed_from_response(self):
        """Test that reasoning/thinking content is correctly parsed from API response."""
        provider = make_provider(model="gpt-4o")

        async def mock_stream():
            # First chunk with reasoning
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = "Let me reason about this..."
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Second chunk with final answer
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta.content = "Final answer"
            choice2.delta.reasoning_content = None
            choice2.delta.tool_calls = None
            choice2.finish_reason = "stop"
            chunk2.choices = [choice2]
            chunk2.usage = MagicMock()
            chunk2.usage.prompt_tokens = 10
            chunk2.usage.completion_tokens = 5
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            from agent_kernel.providers.base import StreamEventType

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Think about something"}],
            ):
                events.append(event)

            # Verify thinking events are captured
            thinking_events = [e for e in events if e.type == StreamEventType.THINKING_DELTA]
            assert len(thinking_events) > 0
            assert "reason" in thinking_events[0].text.lower()

    def test_model_info_supports_tools_field(self):
        """Test that ModelInfo has supports_tools field."""
        # Test from catalog
        openai_models = PROVIDER_MODELS.get("openai", [])
        for model in openai_models:
            assert hasattr(model, "supports_tools")
            # OpenAI models in catalog should support tools
            assert model.supports_tools is True

        # Test from provider
        provider = make_provider(model="gpt-4o")
        info = provider.get_model_info()
        assert hasattr(info, "supports_tools")


class TestToolCallingAvailability:
    """Tests for tool calling capability detection."""

    def test_tool_support_from_provider_catalog(self):
        """Test tool support detection from PROVIDER_MODELS catalog."""
        # OpenAI models should support tools
        openai_models = PROVIDER_MODELS.get("openai", [])
        for model in openai_models:
            assert model.supports_tools is True

    def test_ollama_tool_support_from_catalog(self):
        """Test tool support for Ollama models from catalog."""
        ollama_models = PROVIDER_MODELS.get("ollama", [])
        for model in ollama_models:
            # In the catalog, Ollama models are marked as supporting tools
            assert model.supports_tools is True

    def test_provider_get_model_info_tools(self):
        """Test OpenAIProvider.get_model_info() returns correct tool support."""
        provider = make_provider(model="gpt-4o")
        info = provider.get_model_info()
        assert info.supports_tools is True

        provider = make_provider(model="gpt-3.5-turbo")
        info = provider.get_model_info()
        assert info.supports_tools is True

    @pytest.mark.asyncio
    async def test_tool_calling_works_with_tools_parameter(self):
        """Test that tool calling works when tools are provided."""
        from agent_kernel.providers.base import ToolDefinition

        provider = make_provider(model="gpt-4o")

        async def mock_stream():
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta.content = None
            choice.delta.reasoning_content = None

            # Tool call in response
            tc = MagicMock()
            tc.index = 0
            tc.id = "call_123"
            tc.function.name = "echo"
            tc.function.arguments = '{"message": "test"}'
            choice.delta.tool_calls = [tc]
            choice.finish_reason = "tool_calls"
            chunk.choices = [choice]
            chunk.usage = MagicMock()
            chunk.usage.prompt_tokens = 10
            chunk.usage.completion_tokens = 5
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            from agent_kernel.providers.base import StreamEventType

            tools = [
                ToolDefinition(
                    name="echo",
                    description="Echo input",
                    parameters={
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                    },
                )
            ]

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Use tool"}],
                tools=tools,
            ):
                events.append(event)

            # Verify tool call events are emitted
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 1
            assert start_events[0].tool_name == "echo"

    @pytest.mark.asyncio
    async def test_tools_parameter_accepted_by_create_message(self):
        """Test that tools parameter is accepted without error."""
        provider = make_provider(model="gpt-4o")

        from agent_kernel.providers.base import ToolDefinition

        tools = [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters={"type": "object", "properties": {}},
            )
        ]

        # This should not raise - tools are accepted
        async def mock_stream():
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta.content = "test"
            choice.delta.reasoning_content = None
            choice.delta.tool_calls = None
            choice.finish_reason = "stop"
            chunk.choices = [choice]
            chunk.usage = MagicMock()
            chunk.usage.prompt_tokens = 10
            chunk.usage.completion_tokens = 5
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            async for _ in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                tools=tools,
            ):
                pass


class TestStreamingSupport:
    """Tests for streaming capability verification."""

    def test_streaming_enabled_by_default(self):
        """Test that streaming is enabled by default in provider."""
        provider = make_provider(model="gpt-4o")
        assert provider._stream is True

    @pytest.mark.asyncio
    async def test_streaming_can_be_disabled(self):
        """Test that streaming can be disabled via parameter."""
        provider = make_provider(model="gpt-4o", provider_name="custom")

        # For non-streaming, return response directly (not as async generator)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            from agent_kernel.providers.base import StreamEventType

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                stream=False,
            ):
                events.append(event)

            # Should still get text event
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert len(text_events) == 1

            # Verify stream=False was passed
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs.get("stream") is False

    @pytest.mark.asyncio
    async def test_streaming_events_emitted_correctly(self):
        """Test that streaming events are emitted correctly."""
        provider = make_provider(model="gpt-4o")

        async def mock_stream():
            # Chunk 1
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta.content = "Hello "
            choice1.delta.reasoning_content = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Chunk 2 (final)
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta.content = "World"
            choice2.delta.reasoning_content = None
            choice2.delta.tool_calls = None
            choice2.finish_reason = "stop"
            chunk2.choices = [choice2]
            chunk2.usage = MagicMock()
            chunk2.usage.prompt_tokens = 10
            chunk2.usage.completion_tokens = 5
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            from agent_kernel.providers.base import StreamEventType

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                stream=True,
            ):
                events.append(event)

            # Verify streaming events
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert len(text_events) == 2
            assert text_events[0].text == "Hello "
            assert text_events[1].text == "World"

            # Verify message end
            end_events = [e for e in events if e.type == StreamEventType.MESSAGE_END]
            assert len(end_events) == 1

    @pytest.mark.asyncio
    async def test_stream_parameter_per_call_override(self):
        """Test that stream parameter can be overridden per call."""
        provider = make_provider(model="gpt-4o")

        # For non-streaming, return response directly
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        # Default is streaming
        assert provider._stream is True

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Override to non-streaming
            async for _ in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
                stream=False,
            ):
                pass

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs.get("stream") is False


class TestRegistryCapabilityDetection:
    """Tests for capability detection via ProviderRegistry."""

    def test_list_models_returns_model_info(self):
        """Test that list_models returns ModelInfo objects with capability data."""
        models = registry.list_models("openai")

        assert len(models) > 0
        for model in models:
            assert isinstance(model, ModelInfo)
            assert hasattr(model, "supports_vision")
            assert hasattr(model, "supports_tools")
            assert hasattr(model, "max_context")

    def test_list_models_for_different_providers(self):
        """Test listing models for different providers."""
        for provider_name in PROVIDER_MODELS.keys():
            models = registry.list_models(provider_name)
            assert len(models) > 0
            for model in models:
                assert model.provider == provider_name

    def test_unknown_provider_returns_empty_list(self):
        """Test that unknown provider returns empty list."""
        models = registry.list_models("unknown-provider")
        assert models == []
