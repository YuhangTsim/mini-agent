"""Tests for open_agent.core.session.SessionProcessor."""

from __future__ import annotations


from agent_kernel.tool_calling import TOOL_CALLING_FAILURE_PREFIX
from agent_kernel.providers.base import StreamEvent, StreamEventType
from agent_kernel.tools.base import BaseTool, ToolRegistry, ToolResult
from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig
from open_agent.core.session import SessionCallbacks, SessionProcessor
from open_agent.persistence.models import AgentRun, AgentRunStatus, Session


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

    async def test_top_level_transcript_stores_visible_messages(
        self, open_store, event_bus, hook_registry
    ):
        await open_store.create_session(Session(id="sess-1", title="Transcript"))
        provider = MockProvider([make_text_events("Visible reply.")])
        agent = make_agent()
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
            persist_session_transcript=True,
        )
        await processor.process(agent_run=run, user_message="Store me visibly")

        transcript = await open_store.get_session_messages(run.session_id)
        assert [message.role.value for message in transcript] == ["user", "assistant"]
        assert [message.content for message in transcript] == [
            "Store me visibly",
            "Visible reply.",
        ]


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

    async def test_recovery_after_invalid_tool_turn(self, open_store, event_bus, hook_registry):
        provider = MockProvider([
            make_tool_call_events("echo", "NOT VALID JSON", call_id="tc-bad"),
            make_tool_call_events("echo", '{"message": "fixed"}', call_id="tc-good"),
            make_text_events("Recovered after retry."),
        ])
        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Recover")

        assert result == "Recovered after retry."
        assert run.status == AgentRunStatus.COMPLETED
        tool_calls = await open_store.get_tool_calls(run.id)
        assert [tc.status for tc in tool_calls] == ["error", "success"]

    async def test_two_invalid_tool_turns_return_structured_failure(
        self, open_store, event_bus, hook_registry
    ):
        provider = MockProvider([
            make_tool_call_events("echo", "NOT VALID JSON", call_id="tc-001"),
            make_tool_call_events("echo", "STILL BAD JSON", call_id="tc-002"),
            make_text_events("Should not be reached."),
        ])
        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Keep failing")

        assert result.startswith(TOOL_CALLING_FAILURE_PREFIX)
        assert run.status == AgentRunStatus.FAILED
        assert "invalid_tool_turns" in result
        assert provider._call_index == 2

    async def test_tool_calls_are_written_to_session_transcript(
        self, open_store, event_bus, hook_registry
    ):
        await open_store.create_session(Session(id="sess-1", title="Transcript"))
        provider = MockProvider([
            make_tool_call_events("echo", '{"message": "hello"}'),
            make_text_events("Done with tool."),
        ])
        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(
            agent,
            provider,
            registry,
            open_store,
            event_bus,
            hook_registry,
            persist_session_transcript=True,
        )
        await processor.process(agent_run=run, user_message="Use echo")

        transcript = await open_store.get_session_messages(run.session_id)
        assert [message.role.value for message in transcript] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]
        assert transcript[1].tool_calls is not None
        assert transcript[1].tool_calls[0]["function"]["name"] == "echo"
        assert transcript[2].tool_call_id == "tc-001"
        assert transcript[2].content == "Echo: hello"
        assert transcript[3].content == "Done with tool."

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

    async def test_report_result_is_normalized_in_session_transcript(
        self, open_store, event_bus, hook_registry
    ):
        await open_store.create_session(Session(id="sess-1", title="Transcript"))
        provider = MockProvider([
            make_tool_call_events("report_result", '{"result": "final answer"}'),
        ])
        agent = make_agent()
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
            persist_session_transcript=True,
        )
        await processor.process(agent_run=run, user_message="Report something")

        transcript = await open_store.get_session_messages(run.session_id)
        assert [message.role.value for message in transcript] == ["user", "assistant"]
        assert [message.content for message in transcript] == [
            "Report something",
            "final answer",
        ]


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

    async def test_child_processor_does_not_write_session_transcript(
        self, open_store, event_bus, hook_registry
    ):
        await open_store.create_session(Session(id="sess-1", title="Transcript"))
        provider = MockProvider([make_text_events("child result")])
        agent = make_agent()
        registry = ToolRegistry()
        child_run = make_agent_run()
        child_run.parent_run_id = "parent-run"
        await open_store.create_agent_run(child_run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=child_run, user_message="child work")

        transcript = await open_store.get_session_messages(child_run.session_id)
        assert transcript == []


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


# ---------------------------------------------------------------------------
# Thinking helpers
# ---------------------------------------------------------------------------


def make_thinking_then_text_events(
    thinking: str, text: str, input_tokens: int = 10, output_tokens: int = 5
):
    return [
        StreamEvent(type=StreamEventType.THINKING_DELTA, text=thinking),
        StreamEvent(type=StreamEventType.TEXT_DELTA, text=text),
        StreamEvent(
            type=StreamEventType.MESSAGE_END,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    ]


def make_thinking_then_tool_events(
    thinking: str, tool_name: str, tool_args: str, call_id: str = "tc-001"
):
    return [
        StreamEvent(type=StreamEventType.THINKING_DELTA, text=thinking),
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


# ---------------------------------------------------------------------------
# Thinking tests
# ---------------------------------------------------------------------------


class TestSessionProcessorThinking:
    async def test_thinking_then_text_returns_text(self, open_store, event_bus, hook_registry):
        """Thinking is accumulated but final result is just the text."""
        provider = MockProvider([make_thinking_then_text_events("Let me think...", "The answer.")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Question")

        assert result == "The answer."

    async def test_thinking_callback_fires(self, open_store, event_bus, hook_registry):
        """on_thinking_delta callback receives thinking tokens."""
        received = []

        async def on_thinking(text):
            received.append(text)

        provider = MockProvider([make_thinking_then_text_events("deep thought", "answer")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        callbacks = SessionCallbacks(on_thinking_delta=on_thinking)
        processor = make_processor(
            agent, provider, registry, open_store, event_bus, hook_registry, callbacks=callbacks
        )
        await processor.process(agent_run=run, user_message="Think")

        assert "deep thought" in received

    async def test_thinking_not_in_conversation_history(
        self, open_store, event_bus, hook_registry
    ):
        """Thinking content should NOT be appended to conversation sent to LLM."""
        provider = MockProvider([make_thinking_then_text_events("secret thought", "visible")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Hi")

        # The conversation passed to the provider should not contain thinking
        call_kwargs = provider.calls[0]
        messages = call_kwargs["messages"]
        for msg in messages:
            content = msg.get("content", "")
            if content:
                assert "secret thought" not in content

    async def test_thinking_stored_as_message_part(self, open_store, event_bus, hook_registry):
        """Thinking is persisted as a MessagePart with part_type='thinking'."""
        provider = MockProvider([make_thinking_then_text_events("reasoning here", "answer")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="Store thinking")

        # Get the assistant message and check its parts
        messages = await open_store.get_messages(run.id)
        assistant_msgs = [m for m in messages if m.role.value == "assistant"]
        assert len(assistant_msgs) >= 1

        parts = await open_store.get_message_parts(assistant_msgs[0].id)
        thinking_parts = [p for p in parts if p.part_type == "thinking"]
        assert len(thinking_parts) == 1
        assert thinking_parts[0].content == "reasoning here"

    async def test_thinking_not_written_to_session_transcript(
        self, open_store, event_bus, hook_registry
    ):
        await open_store.create_session(Session(id="sess-1", title="Transcript"))
        provider = MockProvider([make_thinking_then_text_events("secret thought", "visible")])
        agent = make_agent()
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
            persist_session_transcript=True,
        )
        await processor.process(agent_run=run, user_message="Hi")

        transcript = await open_store.get_session_messages(run.session_id)
        assert [message.content for message in transcript] == ["Hi", "visible"]
        for message in transcript:
            assert "secret thought" not in message.content

    async def test_thinking_with_tool_calls(self, open_store, event_bus, hook_registry):
        """Thinking before tool calls: thinking is accumulated, tool executes."""
        provider = MockProvider([
            make_thinking_then_tool_events("planning...", "echo", '{"message": "hi"}'),
            make_text_events("Done."),
        ])
        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Use tool with thinking")

        assert result == "Done."
        # Thinking should be stored as message part on the tool-call assistant message
        messages = await open_store.get_messages(run.id)
        assistant_msgs = [m for m in messages if m.role.value == "assistant"]
        assert len(assistant_msgs) >= 1
        parts = await open_store.get_message_parts(assistant_msgs[0].id)
        thinking_parts = [p for p in parts if p.part_type == "thinking"]
        assert len(thinking_parts) == 1
        assert thinking_parts[0].content == "planning..."

    async def test_no_thinking_backward_compat(self, open_store, event_bus, hook_registry):
        """Without thinking events, everything works as before."""
        provider = MockProvider([make_text_events("Just text.")])
        agent = make_agent()
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        result = await processor.process(agent_run=run, user_message="Normal")

        assert result == "Just text."
        messages = await open_store.get_messages(run.id)
        assistant_msgs = [m for m in messages if m.role.value == "assistant"]
        # No thinking parts stored
        for msg in assistant_msgs:
            parts = await open_store.get_message_parts(msg.id)
            thinking_parts = [p for p in parts if p.part_type == "thinking"]
            assert len(thinking_parts) == 0

    async def test_thinking_budget_not_passed_when_none(
        self, open_store, event_bus, hook_registry
    ):
        """When thinking_budget_tokens is None (default), it is passed as None to provider."""
        provider = MockProvider([make_text_events("reply")])
        agent = make_agent()  # thinking_budget_tokens defaults to None
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="hi")

        assert provider.calls[0].get("thinking_budget_tokens") is None

    async def test_thinking_budget_passed_to_provider(self, open_store, event_bus, hook_registry):
        """When thinking_budget_tokens is set, it is forwarded to provider.create_message()."""
        provider = MockProvider([make_thinking_then_text_events("thoughts", "answer")])
        agent = make_agent(thinking_budget_tokens=5000)
        registry = ToolRegistry()
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)
        await processor.process(agent_run=run, user_message="think hard")

        assert provider.calls[0].get("thinking_budget_tokens") == 5000
