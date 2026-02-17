"""Tests for open_agent.core.session.SessionProcessor."""

from __future__ import annotations

import pytest

from agent_kernel.providers.base import StreamEvent, StreamEventType
from agent_kernel.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult
from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig
from open_agent.core.session import SessionCallbacks, SessionProcessor
from open_agent.hooks.registry import HookRegistry
from open_agent.persistence.models import AgentRun, AgentRunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_text_events(text: str, input_tokens: int = 10, output_tokens: int = 5):
    return [
        StreamEvent(type=StreamEventType.TEXT_DELTA, text=text),
        StreamEvent(
            type=StreamEventType.MESSAGE_END,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    ]


def make_tool_call_events(tool_name: str, tool_args: str, call_id: str = "tc-001"):
    return [
        StreamEvent(
            type=StreamEventType.TOOL_CALL_START, tool_call_id=call_id, tool_name=tool_name
        ),
        StreamEvent(
            type=StreamEventType.TOOL_CALL_END,
            tool_call_id=call_id,
            tool_name=tool_name,
            tool_args=tool_args,
        ),
        StreamEvent(type=StreamEventType.MESSAGE_END, input_tokens=10, output_tokens=20),
    ]


class MockProvider:
    def __init__(self, responses: list[list[StreamEvent]]):
        self._responses = list(responses)
        self._call_index = 0
        self.calls: list[dict] = []

    def create_message(self, **kwargs):
        self.calls.append(kwargs)
        events = (
            self._responses[self._call_index]
            if self._call_index < len(self._responses)
            else []
        )
        self._call_index += 1
        return self._stream(events)

    async def _stream(self, events):
        for event in events:
            yield event

    def count_tokens(self, text: str) -> int:
        return len(text.split())


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo input"
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "additionalProperties": False,
    }
    groups = ["read"]
    skip_approval = True

    async def execute(self, params, context):
        return ToolResult.success(f"Echo: {params.get('message', '')}")


class ConcreteAgent(BaseAgent):
    def get_system_prompt(self, context=None) -> str:
        return "You are a test agent."


def make_agent(**kwargs) -> ConcreteAgent:
    config = AgentConfig(role="test_agent", **kwargs)
    return ConcreteAgent(config)


def make_agent_run(session_id: str = "sess-1") -> AgentRun:
    return AgentRun(
        session_id=session_id,
        agent_role="test_agent",
        status=AgentRunStatus.RUNNING,
        description="Test run",
    )


def make_processor(
    agent, provider, tool_registry, store, event_bus, hook_registry, **kwargs
) -> SessionProcessor:
    return SessionProcessor(
        agent=agent,
        provider=provider,
        tool_registry=tool_registry,
        permission_checker=_make_permchecker(),
        hook_registry=hook_registry,
        bus=event_bus,
        store=store,
        working_directory="/tmp",
        **kwargs,
    )


def _make_permchecker():
    from open_agent.tools.permissions import PermissionChecker
    return PermissionChecker()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionProcessorSimple:
    async def test_text_response_returned(self, open_store, event_bus, hook_registry):
        provider = MockProvider([make_text_events("Hello from agent!")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Hello")

        assert result == "Hello from agent!"

    async def test_empty_tool_list_when_agent_has_no_tools(
        self, open_store, event_bus, hook_registry
    ):
        provider = MockProvider([make_text_events("No tools.")])
        agent = make_agent(allowed_tools=["nonexistent"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Hi")

        # LLM was called - tools should be empty (nonexistent not in registry)
        call_args = provider.calls[0]
        assert call_args["tools"] is None or call_args["tools"] == []

    async def test_user_message_stored(self, open_store, event_bus, hook_registry):
        provider = MockProvider([make_text_events("Reply.")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Store me!")

        messages = await open_store.get_messages(run.id)
        assert any(m.content == "Store me!" for m in messages)

    async def test_token_usage_accumulated(self, open_store, event_bus, hook_registry):
        provider = MockProvider([make_text_events("Hi.", input_tokens=15, output_tokens=7)])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Token test")

        assert run.token_usage.input_tokens == 15
        assert run.token_usage.output_tokens == 7

    async def test_agent_run_marked_completed(self, open_store, event_bus, hook_registry):
        provider = MockProvider([make_text_events("Done.")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Finish")

        assert run.status == AgentRunStatus.COMPLETED


class TestSessionProcessorToolCalls:
    async def test_tool_call_executed(self, open_store, event_bus, hook_registry):
        provider = MockProvider([
            make_tool_call_events("echo", '{"message": "hello"}'),
            make_text_events("Done with tool."),
        ])
        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Use echo")

        assert result == "Done with tool."
        tool_calls = await open_store.get_tool_calls(run.id)
        assert any(tc.tool_name == "echo" for tc in tool_calls)

    async def test_unknown_tool_returns_error(self, open_store, event_bus, hook_registry):
        provider = MockProvider([
            make_tool_call_events("unknown_tool", "{}"),
            make_text_events("Handled error."),
        ])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Bad tool")

        assert result == "Handled error."
        tool_calls = await open_store.get_tool_calls(run.id)
        assert any(tc.status == "error" for tc in tool_calls)

    async def test_report_result_breaks_loop(self, open_store, event_bus, hook_registry):
        """report_result tool call terminates the loop immediately."""
        provider = MockProvider([
            make_tool_call_events("report_result", '{"result": "final answer"}'),
            make_text_events("This should not be reached."),
        ])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Report something")

        assert result == "final answer"
        assert run.result == "final answer"
        assert run.status == AgentRunStatus.COMPLETED
        # Provider should only have been called once
        assert provider._call_index == 1


class TestSessionProcessorDelegation:
    async def test_delegate_task_calls_handler(self, open_store, event_bus, hook_registry):
        delegation_calls = []

        async def delegation_handler(from_run, target_role, description):
            delegation_calls.append((target_role, description))
            return "delegation result"

        provider = MockProvider([
            make_tool_call_events(
                "delegate_task",
                '{"agent_role": "explorer", "description": "Find something"}',
            ),
            make_text_events("Delegated successfully."),
        ])
        # Agent can delegate to explorer
        agent = make_agent(can_delegate_to=["explorer"])
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(
            agent,
            provider,
            registry,
            open_store,
            event_bus,
            hook_registry,
            delegation_handler=delegation_handler,
        )
        await processor.process(agent_run=run, user_message="Delegate")

        assert len(delegation_calls) == 1
        assert delegation_calls[0][0] == "explorer"
        assert delegation_calls[0][1] == "Find something"

    async def test_delegate_to_unauthorized_agent_fails(
        self, open_store, event_bus, hook_registry
    ):
        async def delegation_handler(**kwargs):
            return "should not be called"

        provider = MockProvider([
            make_tool_call_events(
                "delegate_task",
                '{"agent_role": "fixer", "description": "Do it"}',
            ),
            make_text_events("Got error, moving on."),
        ])
        # Agent cannot delegate to fixer
        agent = make_agent(can_delegate_to=["explorer"])
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(
            agent,
            provider,
            registry,
            open_store,
            event_bus,
            hook_registry,
            delegation_handler=delegation_handler,
        )
        await processor.process(agent_run=run, user_message="Bad delegation")

        # No exception, but tool result should contain error
        # (the conversation continues because agent gets error result)


class TestSessionProcessorCallbacks:
    async def test_on_text_delta_callback(self, open_store, event_bus, hook_registry):
        received = []

        async def on_delta(text):
            received.append(text)

        provider = MockProvider([make_text_events("Hello world")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        callbacks = SessionCallbacks(on_text_delta=on_delta)
        processor = make_processor(
            agent, provider, registry, open_store, event_bus, hook_registry, callbacks=callbacks
        )
        await processor.process(agent_run=run, user_message="Hi")

        assert "Hello world" in received

    async def test_on_message_end_callback(self, open_store, event_bus, hook_registry):
        usage_received = []

        async def on_end(usage):
            usage_received.append(usage)

        provider = MockProvider([make_text_events("Response.", input_tokens=5, output_tokens=3)])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        callbacks = SessionCallbacks(on_message_end=on_end)
        processor = make_processor(
            agent, provider, registry, open_store, event_bus, hook_registry, callbacks=callbacks
        )
        await processor.process(agent_run=run, user_message="Test")

        assert len(usage_received) >= 1
        assert usage_received[0].input_tokens == 5
