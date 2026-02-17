"""Tests for roo_agent.core.agent.Agent - the core LLM→tool loop."""

from __future__ import annotations

import pytest

from agent_kernel.providers.base import StreamEvent, StreamEventType
from agent_kernel.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult
from roo_agent.config.settings import ApprovalConfig, Settings
from roo_agent.core.agent import Agent, AgentCallbacks
from roo_agent.persistence.models import Task, TaskStatus
from roo_agent.persistence.store import Store
from roo_agent.tools.agent.task_tools import AttemptCompletionTool, SwitchModeTool
from roo_agent.tools.native import get_all_native_tools


class EchoTool(BaseTool):
    """Local echo tool for testing."""

    name = "echo"
    description = "Echo a message"
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
        "additionalProperties": False,
    }
    groups = ["read"]
    skip_approval = True

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        return ToolResult.success(f"Echo: {params.get('message', '')}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_text_events(
    text: str, input_tokens: int = 10, output_tokens: int = 5
) -> list[StreamEvent]:
    return [
        StreamEvent(type=StreamEventType.TEXT_DELTA, text=text),
        StreamEvent(
            type=StreamEventType.MESSAGE_END,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    ]


def make_tool_call_events(
    tool_name: str, tool_args: str, call_id: str = "tc-001"
) -> list[StreamEvent]:
    return [
        StreamEvent(
            type=StreamEventType.TOOL_CALL_START,
            tool_call_id=call_id,
            tool_name=tool_name,
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

    async def _stream(self, events: list[StreamEvent]):
        for event in events:
            yield event

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def make_settings(tmp_path) -> Settings:
    s = Settings()
    s.working_directory = str(tmp_path)
    # Auto-approve everything so tests don't hang waiting for approval
    s.approval = ApprovalConfig(policies={"*": "auto_approve"})
    return s


async def make_store(tmp_path) -> Store:
    store = Store(str(tmp_path / "roo.db"))
    await store.initialize()
    return store


def make_registry(*tools) -> ToolRegistry:
    reg = ToolRegistry()
    for tool in tools:
        reg.register(tool)
    return reg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentSimpleRun:
    async def test_simple_text_response(self, tmp_path):
        provider = MockProvider([make_text_events("Hello!")])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry()

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        result = await agent.run(
            task=task,
            user_message="Hi",
            conversation=[],
            system_prompt="You are helpful.",
        )

        assert result == "Hello!"
        await store.close()

    async def test_stores_user_message(self, tmp_path):
        provider = MockProvider([make_text_events("Response.")])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry()

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        await agent.run(
            task=task,
            user_message="Hello there",
            conversation=[],
            system_prompt="You are helpful.",
        )

        messages = await store.get_messages(task.id)
        assert any(m.content == "Hello there" for m in messages)
        await store.close()

    async def test_conversation_history_included_in_llm_call(self, tmp_path):
        provider = MockProvider([make_text_events("Response.")])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry()

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        prior_conversation = [{"role": "user", "content": "previous message"}]
        await agent.run(
            task=task,
            user_message="New message",
            conversation=prior_conversation,
            system_prompt="You are helpful.",
        )

        call_args = provider.calls[0]
        messages = call_args["messages"]
        assert any(m["content"] == "previous message" for m in messages)
        await store.close()


class TestAgentToolCalls:
    async def test_tool_call_executed(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events("echo", '{"message": "test input"}'),
            make_text_events("Done."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(EchoTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        result = await agent.run(
            task=task,
            user_message="Echo something",
            conversation=[],
            system_prompt="You are helpful.",
        )

        assert result == "Done."
        tool_calls = await store.get_tool_calls(task.id)
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "echo"
        assert tool_calls[0].status == "success"
        await store.close()

    async def test_unknown_tool_returns_error_result(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events("nonexistent_tool", "{}"),
            make_text_events("Handled."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry()

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        result = await agent.run(
            task=task, user_message="Try unknown", conversation=[], system_prompt="."
        )

        assert result == "Handled."
        tool_calls = await store.get_tool_calls(task.id)
        assert any(tc.status == "error" for tc in tool_calls)
        await store.close()

    async def test_invalid_json_args_returns_error(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events("echo", "NOT VALID JSON"),
            make_text_events("Recovered."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(EchoTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        result = await agent.run(
            task=task, user_message="Bad args", conversation=[], system_prompt="."
        )
        assert result == "Recovered."
        await store.close()


class TestAgentSignals:
    async def test_attempt_completion_marks_task_done(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events(
                "attempt_completion", '{"result": "All done!"}', call_id="tc-ac"
            ),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(AttemptCompletionTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        result = await agent.run(
            task=task, user_message="Complete it", conversation=[], system_prompt="."
        )

        assert result == "All done!"
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "All done!"
        await store.close()

    async def test_switch_mode_updates_mode(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events(
                "switch_mode",
                '{"mode_slug": "ask", "reason": "need to explain"}',
                call_id="tc-sm",
            ),
            make_text_events("Now in ask mode."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(SwitchModeTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        await agent.run(
            task=task, user_message="Switch mode", conversation=[], system_prompt="."
        )

        # Mode should have been updated on the task
        assert task.mode == "ask"
        await store.close()

    async def test_switch_to_unknown_mode_continues(self, tmp_path):
        """Switching to unknown mode gracefully continues instead of crashing."""
        provider = MockProvider([
            make_tool_call_events(
                "switch_mode",
                '{"mode_slug": "nonexistent", "reason": "test"}',
                call_id="tc-sm-bad",
            ),
            make_text_events("Continued."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(SwitchModeTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        # Should not raise
        result = await agent.run(
            task=task, user_message="Bad switch", conversation=[], system_prompt="."
        )
        assert result == "Continued."
        await store.close()


class TestAgentApprovalFlow:
    async def test_denied_tool_blocked_by_policy(self, tmp_path):
        provider = MockProvider([
            make_tool_call_events("echo", '{"message": "hi"}'),
            make_text_events("Blocked result."),
        ])
        settings = make_settings(tmp_path)
        # Deny all tools
        settings.approval = ApprovalConfig(policies={"*": "deny"})
        store = await make_store(tmp_path)
        registry = make_registry(EchoTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        await agent.run(
            task=task, user_message="Try tool", conversation=[], system_prompt="."
        )

        # Tool call should be recorded as denied
        tool_calls = await store.get_tool_calls(task.id)
        assert any(tc.status == "denied" for tc in tool_calls)
        await store.close()

    async def test_mode_file_restriction_blocks_edit(self, tmp_path):
        from agent_kernel.tools.native.file_ops import WriteFileTool

        provider = MockProvider([
            make_tool_call_events("write_file", '{"path": "test.py", "content": "x"}'),
            make_text_events("Blocked."),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry(WriteFileTool())

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        # plan mode restricts edits to .md/.txt files
        task = Task(mode="plan", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        await agent.run(
            task=task, user_message="Write py file", conversation=[], system_prompt="."
        )

        # Should be blocked by file restriction
        tool_calls = await store.get_tool_calls(task.id)
        assert any(tc.status == "error" for tc in tool_calls)
        await store.close()


class TestAgentTokenTracking:
    async def test_token_usage_accumulated(self, tmp_path):
        provider = MockProvider([
            make_text_events("Response 1.", input_tokens=10, output_tokens=5),
        ])
        settings = make_settings(tmp_path)
        store = await make_store(tmp_path)
        registry = make_registry()

        agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
        task = Task(mode="code", status=TaskStatus.ACTIVE, working_directory=str(tmp_path))
        await store.create_task(task)

        await agent.run(
            task=task, user_message="Hi", conversation=[], system_prompt="."
        )

        assert task.token_usage.input_tokens == 10
        assert task.token_usage.output_tokens == 5
        await store.close()
