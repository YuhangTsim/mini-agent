"""Shared test fixtures for the mini-agent test suite."""

from __future__ import annotations

import pytest

from agent_kernel.providers.base import StreamEvent, StreamEventType
from agent_kernel.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult
from open_agent.bus.bus import EventBus
from open_agent.hooks.registry import HookRegistry
from open_agent.persistence.store import Store as OpenAgentStore
from roo_agent.persistence.store import Store as RooAgentStore


# ---------------------------------------------------------------------------
# Dummy tools for testing
# ---------------------------------------------------------------------------


class EchoTool(BaseTool):
    """A simple tool that echoes its input."""

    name = "echo"
    description = "Echo a message"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Message to echo"},
        },
        "required": ["message"],
        "additionalProperties": False,
    }
    groups = ["read"]
    skip_approval = True

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        return ToolResult.success(f"Echo: {params.get('message', '')}")


class FailTool(BaseTool):
    """A tool that always fails."""

    name = "fail_tool"
    description = "Always fails"
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}
    groups = ["edit"]
    skip_approval = True

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        return ToolResult.failure("Tool always fails")


# ---------------------------------------------------------------------------
# Stream event helpers
# ---------------------------------------------------------------------------


def make_text_events(
    text: str, input_tokens: int = 10, output_tokens: int = 5
) -> list[StreamEvent]:
    """Create a simple text-only response stream."""
    return [
        StreamEvent(type=StreamEventType.TEXT_DELTA, text=text),
        StreamEvent(
            type=StreamEventType.MESSAGE_END,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    ]


def make_tool_call_events(
    tool_name: str,
    tool_args: str,
    tool_call_id: str = "tc-001",
) -> list[StreamEvent]:
    """Create a stream that makes a single tool call."""
    return [
        StreamEvent(
            type=StreamEventType.TOOL_CALL_START,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        ),
        StreamEvent(
            type=StreamEventType.TOOL_CALL_END,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args,
        ),
        StreamEvent(type=StreamEventType.MESSAGE_END, input_tokens=10, output_tokens=20),
    ]


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def hook_registry():
    return HookRegistry()


@pytest.fixture
def tool_registry():
    reg = ToolRegistry()
    reg.register(EchoTool())
    reg.register(FailTool())
    return reg


@pytest.fixture
async def open_store(tmp_path):
    store = OpenAgentStore(str(tmp_path / "open_agent.db"))
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
async def roo_store(tmp_path):
    store = RooAgentStore(str(tmp_path / "roo_agent.db"))
    await store.initialize()
    yield store
    await store.close()
