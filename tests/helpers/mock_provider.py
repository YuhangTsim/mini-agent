"""Mock provider helper for tests."""

from __future__ import annotations

from agent_kernel.providers.base import ModelInfo, StreamEvent


class MockProvider:
    """Deterministic LLM provider returning pre-configured stream responses."""

    def __init__(self, responses: list[list[StreamEvent]] | None = None):
        self._responses = responses or []
        self._call_count = 0
        self.calls: list[dict] = []

    def create_message(self, **kwargs):
        self.calls.append(kwargs)
        events = (
            self._responses[self._call_count]
            if self._call_count < len(self._responses)
            else []
        )
        self._call_count += 1
        return self._stream(events)

    async def _stream(self, events: list[StreamEvent]):
        for event in events:
            yield event

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="mock",
            model_id="mock-model",
            max_context=1000,
            max_output=100,
        )
