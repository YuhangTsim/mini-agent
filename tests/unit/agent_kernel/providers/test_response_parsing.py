"""Tests for provider response format parsing.

Tests various edge cases in provider response parsing including:
- Missing/empty choices
- Empty delta content
- Tool call variations (missing names, interruptions, multiple calls)
- Thinking + tool call combinations
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_kernel.providers.base import StreamEvent, StreamEventType, ToolDefinition
from agent_kernel.providers.openai import OpenAIProvider


def make_provider() -> OpenAIProvider:
    """Create an OpenAIProvider with a fake base_url (no API key validation)."""
    return OpenAIProvider(
        api_key="test-key",
        model="gpt-4o",
        base_url="http://localhost:11434/v1",
        provider_name="custom",
    )


class TestMissingChoices:
    """Tests for responses with missing or empty choices."""

    @pytest.mark.asyncio
    async def test_missing_choices_streaming(self):
        """Streaming response with missing choices - should handle gracefully."""
        provider = make_provider()

        mock_chunk = MagicMock()
        mock_chunk.choices = []
        mock_chunk.usage = None

        with patch.object(provider, "_client") as mock_client:

            async def mock_stream():
                yield mock_chunk
                # Second chunk with usage only
                usage_chunk = MagicMock()
                usage_chunk.choices = []
                usage_chunk.usage = MagicMock()
                usage_chunk.usage.prompt_tokens = 10
                usage_chunk.usage.completion_tokens = 5
                yield usage_chunk

            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)

            # Should still receive MESSAGE_END with usage
            assert any(e.type == StreamEventType.MESSAGE_END for e in events)

    @pytest.mark.asyncio
    async def test_missing_choices_non_streaming(self):
        """Non-streaming response with missing choices - should raise IndexError."""
        provider = make_provider()

        mock_response = MagicMock()
        mock_response.choices = []
        mock_response.usage = None

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            with pytest.raises(IndexError):
                async for _ in provider.create_message(
                    system_prompt="You are helpful.",
                    messages=[{"role": "user", "content": "Hello"}],
                    stream=False,
                ):
                    pass


class TestEmptyDeltaContent:
    """Tests for empty delta content in streaming responses."""

    @pytest.mark.asyncio
    async def test_empty_delta_content_in_stream(self):
        """Streaming with empty delta content should be handled."""
        provider = make_provider()

        # Create mock chunks with empty content in delta
        async def mock_stream():
            # First chunk with empty content
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = ""  # Empty content
            choice1.delta.reasoning_content = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Second chunk with actual content
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = "Hello"
            choice2.delta.reasoning_content = None
            choice2.delta.tool_calls = None
            choice2.finish_reason = "stop"
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)

            # Should still receive the "Hello" text
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert any(e.text == "Hello" for e in text_events)

    @pytest.mark.asyncio
    async def test_multiple_empty_deltas(self):
        """Multiple empty deltas should not break the stream."""
        provider = make_provider()

        async def mock_stream():
            for _ in range(3):
                chunk = MagicMock()
                choice = MagicMock()
                choice.delta = MagicMock()
                choice.delta.content = ""  # Always empty
                choice.delta.reasoning_content = None
                choice.delta.tool_calls = None
                choice.finish_reason = None
                chunk.choices = [choice]
                chunk.usage = None
                yield chunk

            # Final chunk with content
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta = MagicMock()
            choice.delta.content = "Final"
            choice.delta.reasoning_content = None
            choice.delta.tool_calls = None
            choice.finish_reason = "stop"
            chunk.choices = [choice]
            chunk.usage = None
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Hello"}],
            ):
                events.append(event)

            # Should get the final content
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert len(text_events) == 1
            assert text_events[0].text == "Final"


class TestToolCallMissingFunctionName:
    """Tests for tool calls with missing or empty function names."""

    @pytest.mark.asyncio
    async def test_tool_call_with_empty_function_name_streaming(self):
        """Streaming tool call with empty function name should not emit TOOL_CALL_START."""
        provider = make_provider()

        async def mock_stream():
            # Chunk with tool call but empty function name
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta = MagicMock()
            choice.delta.content = None
            choice.delta.reasoning_content = None
            choice.delta.reasoning = None
            choice.delta.tool_calls = []

            # Create a tool call with empty name
            tc = MagicMock()
            tc.index = 0
            tc.id = "call_123"
            tc.function = MagicMock()
            tc.function.name = ""  # Empty name
            tc.function.arguments = '{"message": "hi"}'
            choice.delta.tool_calls = [tc]

            choice.finish_reason = "tool_calls"
            chunk.choices = [choice]
            chunk.usage = None
            yield chunk

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Use tool"}],
                tools=[
                    ToolDefinition(
                        name="echo",
                        description="Echo input",
                        parameters={
                            "type": "object",
                            "properties": {"message": {"type": "string"}},
                        },
                    )
                ],
            ):
                events.append(event)

            # Should not emit TOOL_CALL_START for empty name
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 0

            # But should still have tool call delta with args
            delta_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DELTA]
            assert len(delta_events) == 1


class TestStreamInterruption:
    """Tests for stream interruption mid-tool-call."""

    @pytest.mark.asyncio
    async def test_stream_ends_mid_tool_call(self):
        """Stream that ends without TOOL_CALL_END should handle gracefully."""
        provider = make_provider()

        async def mock_stream():
            # Chunk with partial tool call (start but no end)
            chunk = MagicMock()
            choice = MagicMock()
            choice.delta = MagicMock()
            choice.delta.content = None
            choice.delta.reasoning_content = None

            tc = MagicMock()
            tc.index = 0
            tc.id = "call_123"
            tc.function = MagicMock()
            tc.function.name = "echo"
            tc.function.arguments = '{"message":'
            choice.delta.tool_calls = [tc]

            choice.finish_reason = None  # No finish reason - stream interrupted
            chunk.choices = [choice]
            chunk.usage = None
            yield chunk

            # Stream ends here without sending TOOL_CALL_END

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Use tool"}],
            ):
                events.append(event)

            # Should still emit TOOL_CALL_START and TOOL_CALL_DELTA
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 1
            assert start_events[0].tool_name == "echo"

            delta_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DELTA]
            assert len(delta_events) == 1


class TestMultipleToolCalls:
    """Tests for multiple tool calls in a single response."""

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_streaming(self):
        """Multiple tool calls in streaming response should all be captured."""
        provider = make_provider()

        async def mock_stream():
            # First tool call
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = None

            tc1 = MagicMock()
            tc1.index = 0
            tc1.id = "call_1"
            tc1.function = MagicMock()
            tc1.function.name = "echo"
            tc1.function.arguments = '{"message": "first"}'
            choice1.delta.tool_calls = [tc1]
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Second tool call
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = None
            choice2.delta.reasoning_content = None

            tc2 = MagicMock()
            tc2.index = 1
            tc2.id = "call_2"
            tc2.function = MagicMock()
            tc2.function.name = "search"
            tc2.function.arguments = '{"query": "test"}'
            choice2.delta.tool_calls = [tc2]
            choice2.finish_reason = "tool_calls"
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Use tools"}],
            ):
                events.append(event)

            # Should have 2 tool call starts
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 2
            assert start_events[0].tool_name == "echo"
            assert start_events[1].tool_name == "search"

            # Should have 2 tool call ends
            end_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_END]
            assert len(end_events) == 2


class TestThinkingAndToolCalls:
    """Tests for thinking content combined with tool calls."""

    @pytest.mark.asyncio
    async def test_thinking_then_tool_call_same_response(self):
        """Response with thinking followed by tool call in same response."""
        provider = make_provider()

        async def mock_stream():
            # First chunk: thinking
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = "Let me think about this..."
            choice1.delta.reasoning = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Second chunk: tool call
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = None
            choice2.delta.reasoning_content = None
            choice2.delta.reasoning = None

            tc = MagicMock()
            tc.index = 0
            tc.id = "call_123"
            tc.function = MagicMock()
            tc.function.name = "echo"
            tc.function.arguments = '{"message": "hi"}'
            choice2.delta.tool_calls = [tc]
            choice2.finish_reason = "tool_calls"
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Think and use tool"}],
            ):
                events.append(event)

            # Should have thinking event
            thinking_events = [
                e
                for e in events
                if e.type == StreamEventType.THINKING_DELTA and isinstance(e.text, str)
            ]
            assert len(thinking_events) == 1
            assert "think" in thinking_events[0].text.lower()

            # Should have tool call events
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 1
            assert start_events[0].tool_name == "echo"

            # Verify ordering: thinking comes before tool call
            event_types = [e.type for e in events]
            thinking_idx = event_types.index(StreamEventType.THINKING_DELTA)
            tool_start_idx = event_types.index(StreamEventType.TOOL_CALL_START)
            assert thinking_idx < tool_start_idx

    @pytest.mark.asyncio
    async def test_thinking_interleaved_with_tool_call(self):
        """Thinking content interleaved with tool call deltas."""
        provider = make_provider()

        async def mock_stream():
            # Chunk 1: thinking delta
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = "First thought..."
            choice1.delta.reasoning = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Chunk 2: tool call start
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = None
            choice2.delta.reasoning_content = None
            choice2.delta.reasoning = None

            tc = MagicMock()
            tc.index = 0
            tc.id = "call_123"
            tc.function = MagicMock()
            tc.function.name = "search"
            tc.function.arguments = ""  # Empty start
            choice2.delta.tool_calls = [tc]
            choice2.finish_reason = None
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

            # Chunk 3: more thinking
            chunk3 = MagicMock()
            choice3 = MagicMock()
            choice3.delta = MagicMock()
            choice3.delta.content = None
            choice3.delta.reasoning_content = "Second thought..."
            choice3.delta.reasoning = None
            choice3.delta.tool_calls = None
            choice3.finish_reason = None
            chunk3.choices = [choice3]
            chunk3.usage = None
            yield chunk3

            # Chunk 4: tool call delta (arguments)
            chunk4 = MagicMock()
            choice4 = MagicMock()
            choice4.delta = MagicMock()
            choice4.delta.content = None
            choice4.delta.reasoning_content = None
            choice4.delta.reasoning = None

            tc4 = MagicMock()
            tc4.index = 0
            tc4.id = None  # No new id
            tc4.function = MagicMock()
            tc4.function.name = None  # No new name
            tc4.function.arguments = '{"query": "test"}'
            choice4.delta.tool_calls = [tc4]
            choice4.finish_reason = "tool_calls"
            chunk4.choices = [choice4]
            chunk4.usage = None
            yield chunk4

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Complex interleaved"}],
            ):
                events.append(event)

            # Should have 2 thinking events (filter out MagicMock values)
            thinking_events = [
                e
                for e in events
                if e.type == StreamEventType.THINKING_DELTA and isinstance(e.text, str)
            ]
            assert len(thinking_events) == 2

            # Should have tool events
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 1
            assert start_events[0].tool_name == "search"

            delta_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_DELTA]
            assert len(delta_events) == 1
            assert "test" in delta_events[0].tool_args

            # Verify correct ordering in the stream
            event_types = [e.type for e in events]
            # Order should be: thinking, tool_start, thinking, tool_delta
            assert event_types[0] == StreamEventType.THINKING_DELTA
            assert event_types[1] == StreamEventType.TOOL_CALL_START
            assert event_types[2] == StreamEventType.THINKING_DELTA
            assert event_types[3] == StreamEventType.TOOL_CALL_DELTA

    @pytest.mark.asyncio
    async def test_multiple_thinking_blocks_multiple_tool_calls(self):
        """Complex response with 2+ thinking blocks and 2+ tool calls."""
        provider = make_provider()

        async def mock_stream():
            # Thinking 1
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = "Thinking about step 1..."
            choice1.delta.reasoning = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Tool call 1
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = None
            choice2.delta.reasoning_content = None
            choice2.delta.reasoning = None

            tc1 = MagicMock()
            tc1.index = 0
            tc1.id = "call_1"
            tc1.function = MagicMock()
            tc1.function.name = "echo"
            tc1.function.arguments = '{"message": "first"}'
            choice2.delta.tool_calls = [tc1]
            choice2.finish_reason = None
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

            # Thinking 2
            chunk3 = MagicMock()
            choice3 = MagicMock()
            choice3.delta = MagicMock()
            choice3.delta.content = None
            choice3.delta.reasoning_content = "Now for step 2..."
            choice3.delta.reasoning = None
            choice3.delta.tool_calls = None
            choice3.finish_reason = None
            chunk3.choices = [choice3]
            chunk3.usage = None
            yield chunk3

            # Tool call 2
            chunk4 = MagicMock()
            choice4 = MagicMock()
            choice4.delta = MagicMock()
            choice4.delta.content = None
            choice4.delta.reasoning_content = None
            choice4.delta.reasoning = None

            tc2 = MagicMock()
            tc2.index = 1
            tc2.id = "call_2"
            tc2.function = MagicMock()
            tc2.function.name = "search"
            tc2.function.arguments = '{"query": "second"}'
            choice4.delta.tool_calls = [tc2]
            choice4.finish_reason = "tool_calls"
            chunk4.choices = [choice4]
            chunk4.usage = None
            yield chunk4

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Multiple thinking and tools"}],
            ):
                events.append(event)

            # Should have 2 thinking events (filter out MagicMock values)
            thinking_events = [
                e
                for e in events
                if e.type == StreamEventType.THINKING_DELTA and isinstance(e.text, str)
            ]
            assert len(thinking_events) == 2

            # Should have 2 tool starts
            start_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_START]
            assert len(start_events) == 2
            tool_names = [e.tool_name for e in start_events]
            assert "echo" in tool_names
            assert "search" in tool_names

            # Should have 2 tool ends
            end_events = [e for e in events if e.type == StreamEventType.TOOL_CALL_END]
            assert len(end_events) == 2

            # Verify all content is captured
            full_thinking = " ".join(e.text for e in thinking_events)
            assert "step 1" in full_thinking
            assert "step 2" in full_thinking


class TestThinkingBudgetHandling:
    """Tests for thinking budget exhaustion handling."""

    @pytest.mark.asyncio
    async def test_thinking_budget_runs_out_mid_thinking(self):
        """When budget runs out mid-thinking, should continue gracefully."""
        provider = make_provider()

        async def mock_stream():
            # Large thinking content (simulating budget exhaustion)
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            # Very long reasoning content to simulate budget issues
            choice1.delta.reasoning_content = "A" * 10000  # Large chunk
            choice1.delta.reasoning = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # After "exhaustion", continue with normal text
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = "Here is my answer."
            choice2.delta.reasoning_content = None
            choice2.delta.reasoning = None
            choice2.delta.tool_calls = None
            choice2.finish_reason = "stop"
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Think hard"}],
                thinking_budget_tokens=5000,
            ):
                events.append(event)

            # Should have thinking event (filter out MagicMock values)
            thinking_events = [
                e
                for e in events
                if e.type == StreamEventType.THINKING_DELTA and isinstance(e.text, str)
            ]
            assert len(thinking_events) >= 1

            # Should have text after thinking
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert any("answer" in e.text for e in text_events)

            # Verify no data loss - should get full thinking content
            full_thinking = "".join(e.text for e in thinking_events)
            assert len(full_thinking) > 0

    @pytest.mark.asyncio
    async def test_thinking_then_text_no_loss(self):
        """Thinking followed by text should have no data loss."""
        provider = make_provider()

        async def mock_stream():
            # Thinking chunk
            chunk1 = MagicMock()
            choice1 = MagicMock()
            choice1.delta = MagicMock()
            choice1.delta.content = None
            choice1.delta.reasoning_content = "My thinking process"
            choice1.delta.reasoning = None
            choice1.delta.tool_calls = None
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            chunk1.usage = None
            yield chunk1

            # Text chunk
            chunk2 = MagicMock()
            choice2 = MagicMock()
            choice2.delta = MagicMock()
            choice2.delta.content = "Final answer"
            choice2.delta.reasoning_content = None
            choice2.delta.reasoning = None
            choice2.delta.tool_calls = None
            choice2.finish_reason = "stop"
            chunk2.choices = [choice2]
            chunk2.usage = None
            yield chunk2

        with patch.object(provider, "_client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())

            events = []
            async for event in provider.create_message(
                system_prompt="You are helpful.",
                messages=[{"role": "user", "content": "Think and answer"}],
            ):
                events.append(event)

            # Verify thinking captured (filter out MagicMock values)
            thinking_events = [
                e
                for e in events
                if e.type == StreamEventType.THINKING_DELTA and isinstance(e.text, str)
            ]
            assert len(thinking_events) == 1
            assert thinking_events[0].text == "My thinking process"

            # Verify text captured
            text_events = [e for e in events if e.type == StreamEventType.TEXT_DELTA]
            assert len(text_events) == 1
            assert text_events[0].text == "Final answer"
