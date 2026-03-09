"""Tests for session transcript replay in OpenAgentApp."""

from __future__ import annotations

import copy

from agent_kernel.providers.base import StreamEvent, StreamEventType
from open_agent.config import Settings
from open_agent.core.app import OpenAgentApp


def make_text_events(text: str) -> list[StreamEvent]:
    return [
        StreamEvent(type=StreamEventType.TEXT_DELTA, text=text),
        StreamEvent(type=StreamEventType.MESSAGE_END, input_tokens=10, output_tokens=5),
    ]


class MockProvider:
    def __init__(self, responses: list[list[StreamEvent]]):
        self._responses = responses
        self._call_index = 0
        self.calls: list[dict] = []

    def create_message(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        events = self._responses[self._call_index]
        self._call_index += 1
        return self._stream(events)

    async def _stream(self, events):
        for event in events:
            yield event


async def test_app_replays_session_transcript_across_turns(tmp_path):
    settings = Settings()
    settings.data_dir = str(tmp_path)
    settings.working_directory = str(tmp_path)
    settings.default_agent = "explorer"
    settings.compaction.enabled = False

    app = OpenAgentApp(settings)
    await app.initialize()

    provider = MockProvider(
        [
            make_text_events("Nice to meet you, Alice."),
            make_text_events("Your name is Alice."),
        ]
    )
    app.provider_registry.get_provider = lambda config: provider  # type: ignore[method-assign]

    try:
        first = await app.process_message("My name is Alice", agent_role="explorer")
        second = await app.process_message("What's my name?", agent_role="explorer")
    finally:
        await app.shutdown()

    assert first == "Nice to meet you, Alice."
    assert second == "Your name is Alice."

    second_call_messages = provider.calls[1]["messages"]
    assert [message["role"] for message in second_call_messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert [message["content"] for message in second_call_messages] == [
        "My name is Alice",
        "Nice to meet you, Alice.",
        "What's my name?",
    ]
