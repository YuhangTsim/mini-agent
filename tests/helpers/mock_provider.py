"""Mock provider helper for tests."""

from __future__ import annotations

from typing import Any, AsyncIterator

from agent_kernel.providers.base import ModelInfo, StreamEvent, StreamEventType


class MockProvider:
    """Deterministic LLM provider returning pre-configured stream responses."""

    def __init__(self, responses: list[list[StreamEvent]] | None = None):
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[dict] = []
        # Non-convergence simulation
        self._non_convergence_count = 0
        self._non_convergence_remaining = 0
        # Escalation capture
        self.captured_messages: list[str] = []
        # Configurable failures
        self._failure_mode: str = "none"  # none, silent, partial, error
        # Status tracking
        self.call_count: int = 0
        self.tool_calls_made: list[dict[str, Any]] = []

    def set_non_convergence(self, count: int) -> None:
        """Configure the provider to return invalid tool calls N times consecutively.

        Args:
            count: Number of consecutive invalid tool call responses to return.
        """
        self._non_convergence_count = count
        self._non_convergence_remaining = count

    def get_captured_messages(self) -> list[str]:
        """Retrieve messages that were captured during message flow.

        Returns:
            List of captured message strings.
        """
        return list(self.captured_messages)

    def set_failure_mode(self, mode: str) -> None:
        """Configure the failure mode for create_message.

        Args:
            mode: Failure mode - "none", "silent", "partial", or "error"
        """
        valid_modes = {"none", "silent", "partial", "error"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid failure mode: {mode}. Must be one of {valid_modes}")
        self._failure_mode = mode

    def get_status(self) -> dict[str, Any]:
        """Get the current status metrics of the provider.

        Returns:
            Dictionary containing call_count, tool_calls_made, and other metrics.
        """
        return {
            "call_count": self.call_count,
            "tool_calls_made": list(self.tool_calls_made),
            "non_convergence_remaining": self._non_convergence_remaining,
            "failure_mode": self._failure_mode,
        }

    def create_message(self, **kwargs):
        """Create a message response, respecting non-convergence and failure modes.

        Args:
            **kwargs: Arguments to pass to the message creation.

        Returns:
            Async iterator of StreamEvent objects.
        """
        self.calls.append(kwargs)
        self.call_count += 1

        # Handle failure modes
        if self._failure_mode == "error":
            self._call_count += 1
            raise RuntimeError("Mock provider error mode")

        if self._failure_mode == "silent":
            self._call_count += 1
            return self._stream([])

        if self._failure_mode == "partial":
            self._call_count += 1
            # Return partial data - just a thinking delta without complete tool call
            partial_events = [
                StreamEvent(type=StreamEventType.THINKING_DELTA, text="Partial res"),
            ]
            return self._stream(partial_events)

        # Check non-convergence mode
        if self._non_convergence_remaining > 0:
            self._non_convergence_remaining -= 1
            events = self._create_invalid_tool_call_events()
            self._call_count += 1
            return self._stream(events)

        # Normal response
        events = (
            self._responses[self._call_count] if self._call_count < len(self._responses) else []
        )
        self._call_count += 1
        # Track tool calls from normal responses
        for event in events:
            if event.type in (StreamEventType.TOOL_CALL_START, StreamEventType.TOOL_CALL_DELTA):
                self.tool_calls_made.append(
                    {
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "tool_args": event.tool_args,
                    }
                )
        return self._stream(events)

    def _create_invalid_tool_call_events(self) -> list[StreamEvent]:
        """Create events with invalid tool call JSON for non-convergence testing."""
        # Use invalid JSON that cannot be parsed
        invalid_args = "{invalid json without closing brace"
        return [
            StreamEvent(
                type=StreamEventType.TOOL_CALL_START,
                tool_call_id="invalid_call_1",
                tool_name="test_tool",
            ),
            StreamEvent(
                type=StreamEventType.TOOL_CALL_DELTA,
                tool_call_id="invalid_call_1",
                tool_args=invalid_args,
            ),
            StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call_id="invalid_call_1",
            ),
        ]

    async def _stream(self, events: list[StreamEvent]) -> AsyncIterator[StreamEvent]:
        """Stream events asynchronously.

        Args:
            events: List of StreamEvent objects to yield.

        Yields:
            StreamEvent objects.
        """
        for event in events:
            yield event

    def count_tokens(self, text: str) -> int:
        """Count tokens in text (simple word-based approximation).

        Args:
            text: Text to count tokens in.

        Returns:
            Token count.
        """
        return len(text.split())

    def get_model_info(self) -> ModelInfo:
        """Get model information for this provider.

        Returns:
            ModelInfo object with provider details.
        """
        return ModelInfo(
            provider="mock",
            model_id="mock-model",
            max_context=1000,
            max_output=100,
        )

    def reset(self) -> None:
        """Reset the provider to initial state, clearing all tracking state."""
        self._call_count = 0
        self.call_count = 0
        self.calls.clear()
        self.captured_messages.clear()
        self.tool_calls_made.clear()
        self._non_convergence_count = 0
        self._non_convergence_remaining = 0
        self._failure_mode = "none"
