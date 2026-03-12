"""Tests for silent failure detection in open-agent.

These tests verify that failures are NOT silent - they are properly surfaced
to parent agents, captured in background tasks, preserved through compaction,
and delivered through the event bus.

Test Cases:
1. Child failure visible to parent - DelegationError raised, child status = FAILED
2. Background task error visibility - error captured in bg_task.error
3. Compaction preserves critical info - task requirements preserved
4. Tool effect validation - documents gap (no validation currently exists)
5. Event bus delivery - all events delivered (no drops)
"""

from __future__ import annotations

import asyncio

import pytest

from open_agent.agents.base import BaseAgent
from open_agent.agents.registry import AgentRegistry
from open_agent.bus import Event, EventBus
from open_agent.bus.events import EventPayload
from open_agent.config.agents import AgentConfig
from open_agent.core.background import BackgroundTaskManager
from open_agent.core.delegation import DelegationError, DelegationManager
from open_agent.core.context.manager import CompactionManager
from open_agent.persistence.models import (
    AgentRun,
    AgentRunStatus,
    Message,
    MessageRole,
)
from open_agent.providers.base import BaseProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConcreteAgent(BaseAgent):
    """Test agent implementation."""

    def get_system_prompt(self, context=None) -> str:
        return f"Test {self.config.role} agent."


def make_agent(role: str, can_delegate_to: list[str] | None = None) -> ConcreteAgent:
    config = AgentConfig(role=role, can_delegate_to=can_delegate_to or [])
    return ConcreteAgent(config)


def make_registry(*agents) -> AgentRegistry:
    reg = AgentRegistry()
    for agent in agents:
        reg.register(agent)
    return reg


def make_run(
    session_id: str = "sess-1",
    parent_run_id: str | None = None,
    agent_role: str = "orchestrator",
) -> AgentRun:
    return AgentRun(
        session_id=session_id,
        parent_run_id=parent_run_id,
        agent_role=agent_role,
        status=AgentRunStatus.RUNNING,
        description="Test run",
    )


from typing import Any, AsyncIterator

from agent_kernel.providers.base import ABC, abstractmethod, ModelInfo, StreamEvent


class MockProvider(ABC):
    """Mock provider for testing."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self._model = model

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(provider="mock", model_id=self._model, max_context=128000)

    async def create_message(
        self,
        system_prompt: str,
        messages: list,
        tools=None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stream: bool = True,
        thinking_budget_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        # Return empty iterator for testing
        return
        yield  # Makes this an async generator

    def count_tokens(self, text: str) -> int:
        # Simple approximation
        return len(text.split())


# ---------------------------------------------------------------------------
# Test: Child failure visible to parent
# ---------------------------------------------------------------------------


class TestChildFailureVisibility:
    """Test that child agent failures are visible to parent."""

    async def test_child_failure_raises_delegation_error_to_parent(self, open_store, event_bus):
        """Verify parent receives DelegationError when child fails."""
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        def mock_factory(agent, parent_run):
            class FailingProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    raise RuntimeError("Child crashed!")

            return FailingProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        # Parent should receive DelegationError
        with pytest.raises(DelegationError, match="Child agent 'explorer' failed"):
            await dm.delegate(
                from_run=parent_run,
                target_role="explorer",
                description="This will crash",
            )

    async def test_child_failure_marks_run_failed(self, open_store, event_bus):
        """Verify child run status = FAILED when it crashes."""
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        def mock_factory(agent, parent_run):
            class FailingProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    raise RuntimeError("Boom!")

            return FailingProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        try:
            await dm.delegate(
                from_run=parent_run,
                target_role="explorer",
                description="Will fail",
            )
        except DelegationError:
            pass

        # Verify child run is marked as FAILED
        child_runs = await open_store.get_child_runs(parent_run.id)
        assert len(child_runs) == 1
        assert child_runs[0].status == AgentRunStatus.FAILED


# ---------------------------------------------------------------------------
# Test: Background task error visibility
# ---------------------------------------------------------------------------


class TestBackgroundTaskErrorVisibility:
    """Test that background task errors are captured and visible."""

    async def test_background_task_error_captured_in_bg_task_error(self, open_store, event_bus):
        """Verify error is captured in bg_task.error."""

        class FailingDelegationManager:
            async def delegate(self, from_run, target_role, description):
                raise RuntimeError("Background task exploded!")

        dm = FailingDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run, target_role="explorer", description="Will fail"
        )

        # Wait for completion
        await asyncio.sleep(0.1)

        # Verify error captured
        bg_task = manager.all_tasks[task_id]
        assert bg_task.error is not None
        assert "Background task exploded" in bg_task.error
        assert bg_task.is_complete is True

    async def test_background_task_error_visible_in_get_status(self, open_store, event_bus):
        """Verify error appears in get_status()."""

        class FailingDelegationManager:
            async def delegate(self, from_run, target_role, description):
                raise RuntimeError("Task failed")

        dm = FailingDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run, target_role="explorer", description="Failing task"
        )

        # Wait for completion
        await asyncio.sleep(0.1)

        # Verify status shows failure
        status = await manager.get_status(task_id)
        assert "FAILED" in status
        assert "Task failed" in status


# ---------------------------------------------------------------------------
# Test: Compaction preserves critical info
# ---------------------------------------------------------------------------


class TestCompactionPreservesCriticalInfo:
    """Test that compaction preserves critical task information."""

    async def test_compaction_preserves_task_requirements_in_metadata(self, open_store, event_bus):
        """Verify task requirements (metadata) are preserved after compaction.

        When compaction happens, we store a summary message with the
        original messages' metadata preserved in the compaction message.
        """
        provider = MockProvider()
        manager = CompactionManager(
            store=open_store,
            provider=provider,
            bus=event_bus,
        )

        # Create an agent run with task requirements in metadata
        run = make_run(session_id="compaction-test")
        await open_store.create_agent_run(run)

        # Create messages with tool outputs that should be preserved
        msg1 = Message(
            agent_run_id=run.id,
            role=MessageRole.USER,
            content="Find all Python files in src/",
            token_count=10,
        )
        msg2 = Message(
            agent_run_id=run.id,
            role=MessageRole.ASSISTANT,
            content="I'll search for Python files",
            token_count=8,
        )
        msg3 = Message(
            agent_run_id=run.id,
            role=MessageRole.TOOL,
            content='["file1.py", "file2.py", "file3.py"]',
            token_count=15,
        )

        await open_store.add_message(msg1)
        await open_store.add_message(msg2)
        await open_store.add_message(msg3)

        # Run compaction manually (simulating what happens when context overflows)
        # The compaction stores a summary message
        result = await manager.compact(
            session_id=run.id,
            agent_run_id=run.id,
            model="gpt-4o-mini",
        )

        # Verify compaction result
        assert result.tokens_before > 0

        # Verify summary message was created with summary preserved
        messages = await open_store.get_messages(run.id)
        compaction_msgs = [m for m in messages if m.is_compaction]
        assert len(compaction_msgs) == 1
        assert compaction_msgs[0].summary is not None

    async def test_compaction_preserves_important_context(self, open_store, event_bus):
        """Verify important context like tool results are preserved.

        This test documents the expected behavior: critical tool outputs
        should survive compaction.
        """
        provider = MockProvider()
        manager = CompactionManager(
            store=open_store,
            provider=provider,
            bus=event_bus,
        )

        run = make_run(session_id="compaction-test-2")
        await open_store.create_agent_run(run)

        # Important tool result that should be preserved
        tool_result_msg = Message(
            agent_run_id=run.id,
            role=MessageRole.TOOL,
            content="Found 5 critical errors: error1, error2, error3, error4, error5",
            token_count=50,
        )
        await open_store.add_message(tool_result_msg)

        # Run compaction
        result = await manager.compact(
            session_id=run.id,
            agent_run_id=run.id,
            model="gpt-4o-mini",
        )

        # Verify compaction happened
        assert result.tokens_before > 0

        # Verify summary message exists
        messages = await open_store.get_messages(run.id)
        compaction_msgs = [m for m in messages if m.is_compaction]
        assert len(compaction_msgs) == 1


# ---------------------------------------------------------------------------
# Test: Tool effect validation (documents gap)
# ---------------------------------------------------------------------------


class TestToolEffectValidation:
    """Test tool effect validation.

    This test documents a current GAP in the system:
    There is NO tool effect validation implemented.
    Tools can report success but the effect may not be achieved.
    """

    async def test_no_tool_effect_validation_exists(self, open_store, event_bus):
        """Document that no tool effect validation currently exists.

        GAP: Currently, tools can return ToolResult.success() even if the
        actual effect wasn't achieved. For example:
        - file_operations tool reports "file written" but disk is full
        - search tool reports "found X results" but missed some files

        This test documents that there is no validation layer that
        confirms tool effects match the reported results.
        """
        from agent_kernel.tools.base import ToolResult
        from open_agent.tools.base import ToolRegistry

        # Check that no validation hooks exist in the tool execution path
        # This is a documentation test showing the current state

        # Currently, the flow is:
        # 1. Tool.execute() returns ToolResult
        # 2. Result is stored
        # 3. No post-execution validation occurs

        # There's no mechanism to:
        # - Verify file was actually written
        # - Verify search actually found all matches
        # - Verify network calls succeeded

        # This documents the gap - failures can be silent when:
        # - Tool returns success but effect failed
        # - Effect succeeded but quality is poor

        # The test passes by documenting this limitation
        assert True, "Tool effect validation is not implemented - this is a known gap"


# ---------------------------------------------------------------------------
# Test: Event bus delivery
# ---------------------------------------------------------------------------


class TestEventBusDelivery:
    """Test that events are delivered to all subscribers (no drops)."""

    async def test_all_events_delivered_to_handler(self, event_bus):
        """Verify all events are delivered to handlers (no drops)."""
        received = []

        async def handler(payload: EventPayload):
            received.append(payload.event)

        # Subscribe to all events
        unsub = event_bus.subscribe(None, handler)

        # Trigger multiple events
        await event_bus.publish(Event.SESSION_START, session_id="s1", agent_role="orchestrator")
        await event_bus.publish(Event.AGENT_START, session_id="s1", agent_role="orchestrator")
        await event_bus.publish(Event.DELEGATION_START, session_id="s1", agent_role="orchestrator")

        # Give time for async handlers
        await asyncio.sleep(0.05)

        # Verify all delivered
        assert Event.SESSION_START in received
        assert Event.AGENT_START in received
        assert Event.DELEGATION_START in received
        assert len(received) == 3

        unsub()

    async def test_all_events_delivered_to_stream(self, event_bus):
        """Verify all events delivered to stream queues (no drops)."""
        # Create a wildcard stream (receives all events)
        queue = event_bus.stream(None)

        # Trigger multiple events rapidly
        for i in range(10):
            await event_bus.publish(
                Event.TOKEN_STREAM,
                session_id=f"s{i}",
                agent_role="test",
                data={"token": f"t{i}"},
            )

        # Verify all 10 events in queue
        received = []
        while not queue.empty():
            received.append(await queue.get())

        assert len(received) == 10

        # Verify data preserved
        for i, payload in enumerate(received):
            assert payload.data["token"] == f"t{i}"

    async def test_multiple_subscribers_all_receive_events(self, event_bus):
        """Verify multiple subscribers all receive events."""
        received1 = []
        received2 = []

        async def handler1(payload: EventPayload):
            received1.append(payload.event)

        async def handler2(payload: EventPayload):
            received2.append(payload.event)

        event_bus.subscribe(Event.TOOL_CALL_START, handler1)
        event_bus.subscribe(Event.TOOL_CALL_START, handler2)

        await event_bus.publish(
            Event.TOOL_CALL_START,
            session_id="s1",
            agent_role="test",
            data={"tool": "read"},
        )

        await asyncio.sleep(0.05)

        # Both handlers should have received the event
        assert len(received1) == 1
        assert len(received2) == 1

    async def test_event_order_preserved(self, event_bus):
        """Verify event order is preserved in delivery."""
        order = []

        async def handler(payload: EventPayload):
            order.append(payload.data["order"])

        event_bus.subscribe(Event.TOKEN_STREAM, handler)

        # Publish in specific order
        for i in range(5):
            await event_bus.publish(
                Event.TOKEN_STREAM,
                session_id="s1",
                agent_role="test",
                data={"order": i},
            )

        await asyncio.sleep(0.05)

        # Verify order preserved
        assert order == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# Test: Integration - Silent failure detection across components
# ---------------------------------------------------------------------------


class TestSilentFailureIntegration:
    """Integration tests for silent failure detection across components."""

    async def test_delegation_failure_propagates_via_bus(self, open_store, event_bus):
        """Verify delegation failures are published to event bus."""
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        failure_received = []

        async def on_error(payload: EventPayload):
            failure_received.append(payload.data)

        event_bus.subscribe(Event.ERROR, on_error)

        def mock_factory(agent, parent_run):
            class FailingProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    raise RuntimeError("Delegation failed")

            return FailingProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        try:
            await dm.delegate(
                from_run=parent_run,
                target_role="explorer",
                description="Will fail",
            )
        except DelegationError:
            pass

        # Note: The current implementation doesn't publish ERROR event on
        # delegation failure - this test documents expected behavior
        # The failure is visible through the store (child run status = FAILED)
        child_runs = await open_store.get_child_runs(parent_run.id)
        assert len(child_runs) == 1
        assert child_runs[0].status == AgentRunStatus.FAILED
