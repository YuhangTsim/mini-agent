"""Tests for non-convergence escalation behavior in SessionProcessor.

These tests document the current behavior where the agent terminates with FAILED
status after 2 consecutive invalid tool turns. Future work should implement
escalation to a more capable agent instead of simple termination.
"""

from __future__ import annotations

import pytest

from agent_kernel.tool_calling import (
    DEFAULT_INVALID_TOOL_TURN_LIMIT,
    TOOL_CALLING_FAILURE_PREFIX,
)
from agent_kernel.providers.base import StreamEvent, StreamEventType
from agent_kernel.tools.base import BaseTool, ToolRegistry, ToolResult
from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig
from open_agent.core.session import SessionProcessor
from open_agent.persistence.models import AgentRun, AgentRunStatus

from tests.helpers.mock_provider import MockProvider


# ---------------------------------------------------------------------------
# Helpers
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
    call_id: str = "tc-001",
) -> list[StreamEvent]:
    """Create a stream that makes a single tool call."""
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

    async def execute(self, params: dict, context) -> ToolResult:
        return ToolResult.success(f"Echo: {params.get('message', '')}")


class ConcreteAgent(BaseAgent):
    """Test agent implementation."""

    def get_system_prompt(self, context=None) -> str:
        return "You are a test agent."


def make_agent(**kwargs) -> ConcreteAgent:
    """Create a test agent with the given config."""
    config = AgentConfig(role="test_agent", **kwargs)
    return ConcreteAgent(config)


def make_agent_run(session_id: str = "sess-1") -> AgentRun:
    """Create a test agent run."""
    return AgentRun(
        session_id=session_id,
        agent_role="test_agent",
        status=AgentRunStatus.RUNNING,
        description="Test run",
    )


def make_processor(agent, provider, tool_registry, store, event_bus, hook_registry, **kwargs):
    """Create a SessionProcessor with standard test configuration."""
    from open_agent.tools.permissions import PermissionChecker

    return SessionProcessor(
        agent=agent,
        provider=provider,
        tool_registry=tool_registry,
        permission_checker=PermissionChecker(),
        hook_registry=hook_registry,
        bus=event_bus,
        store=store,
        working_directory="/tmp",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Non-Convergence Escalation Tests
# ---------------------------------------------------------------------------


class TestNonConvergenceEscalation:
    """Tests for non-convergence termination behavior.

    Current behavior: Agent terminates with FAILED status after 2 consecutive
    invalid tool turns. Future behavior: Should escalate to a more capable agent
    rather than simply failing.
    """

    async def test_non_convergence_terminates_with_failed_status(
        self, open_store, event_bus, hook_registry
    ):
        """After 2 consecutive invalid tool turns (default limit), agent run status = FAILED.

        Current behavior - should escalate to more capable agent in future.
        """
        # Arrange: Use enhanced MockProvider with set_non_convergence
        provider = MockProvider([make_text_events("test")])
        provider.set_non_convergence(3)  # 3 invalid turns

        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Test non-convergence")

        # Assert: Current behavior - terminates with FAILED status
        assert run.status == AgentRunStatus.FAILED
        assert result is not None
        # Note: Future behavior should escalate instead of just failing

    async def test_failure_message_includes_prefix_and_counts(
        self, open_store, event_bus, hook_registry
    ):
        """TOOL_CALLING_FAILURE_PREFIX appears in result with invalid turn counts."""
        # Arrange
        provider = MockProvider([make_text_events("test")])
        provider.set_non_convergence(3)  # Trigger non-convergence

        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Trigger failure")

        # Assert: Failure message contains expected content
        assert TOOL_CALLING_FAILURE_PREFIX in result
        assert "invalid_tool_turns" in result
        assert "invalid_tool_turn_limit" in result

    async def test_invalid_tool_turn_counter_increments_correctly(
        self, open_store, event_bus, hook_registry
    ):
        """Invalid tool turn counter increments on each invalid turn."""
        # Arrange: Provider returns invalid tool call followed by valid
        provider = MockProvider(
            [
                make_tool_call_events("echo", "NOT VALID JSON", call_id="tc-001"),
                make_tool_call_events("echo", "STILL BAD JSON", call_id="tc-002"),
                make_tool_call_events("echo", '{"message": "valid"}', call_id="tc-003"),
                make_text_events("Should not reach here"),
            ]
        )

        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Test counter")

        # Assert: Should fail at 2 invalid turns (default limit)
        assert run.status == AgentRunStatus.FAILED
        assert provider.call_count == 2  # Only 2 LLM calls before termination

    async def test_two_consecutive_invalid_turns_trigger_failure(
        self, open_store, event_bus, hook_registry
    ):
        """Two consecutive invalid tool turns trigger failure.

        This is the core non-convergence behavior - after 2 consecutive invalid
        turns (where all tool results are errors), the agent terminates with FAILED.
        """
        # Arrange: Exactly 2 invalid turns - should trigger failure
        provider = MockProvider(
            [
                make_tool_call_events("echo", "INVALID_1", call_id="tc-001"),
                make_tool_call_events("echo", "INVALID_2", call_id="tc-002"),
                # Should never reach here
                make_text_events("Should not reach"),
            ]
        )

        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Two invalid turns")

        # Assert: Should fail after exactly 2 invalid turns
        assert run.status == AgentRunStatus.FAILED
        assert provider.call_count == 2
        assert TOOL_CALLING_FAILURE_PREFIX in result

    async def test_max_iterations_limit_terminates_loop(self, open_store, event_bus, hook_registry):
        """Loop terminates at max_iterations with completion (not failure).

        Current behavior: When max_iterations is reached, the status is COMPLETED
        (not FAILED) with a message indicating the task may be incomplete.
        """
        # Arrange: Provider returns valid tool calls that never complete (no report_result)
        # Use a tool that always succeeds but never reports result
        provider = MockProvider(
            [
                make_tool_call_events("echo", '{"message": "iter"}', call_id=f"tc-{i:03d}")
                for i in range(60)  # More than max_iterations
            ]
        )
        # Add text responses to continue the loop
        for _ in range(60):
            provider._responses.append(make_text_events("Continuing..."))

        # Use AgentConfig to set max_iterations to a low value for testing
        agent = make_agent(allowed_tools=["echo"], max_iterations=10)
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Run many iterations")

        # Assert: Current behavior - terminates with COMPLETED (not FAILED)
        # Note: This is the current behavior - max_iterations does NOT set FAILED status
        assert run.status == AgentRunStatus.COMPLETED
        assert "maximum iterations" in result.lower()
        assert "may be incomplete" in result.lower()

    async def test_default_invalid_tool_turn_limit_is_two(
        self, open_store, event_bus, hook_registry
    ):
        """DEFAULT_INVALID_TOOL_TURN_LIMIT is 2."""
        # Verify the constant is correctly set
        assert DEFAULT_INVALID_TOOL_TURN_LIMIT == 2

    async def test_non_convergence_triggers_after_exactly_two_invalid_turns(
        self, open_store, event_bus, hook_registry
    ):
        """Non-convergence triggers after exactly 2 invalid turns (default limit)."""
        # Arrange: Provider returns exactly 2 invalid turns then succeeds
        provider = MockProvider(
            [
                make_tool_call_events("echo", "INVALID_1", call_id="tc-001"),
                make_tool_call_events("echo", "INVALID_2", call_id="tc-002"),
                # This should never be reached
                make_tool_call_events("echo", '{"message": "success"}', call_id="tc-003"),
                make_text_events("Should not reach"),
            ]
        )

        agent = make_agent(allowed_tools=["echo"])
        registry = ToolRegistry()
        registry.register(EchoTool())
        run = make_agent_run()
        await open_store.create_agent_run(run)

        processor = make_processor(agent, provider, registry, open_store, event_bus, hook_registry)

        # Act
        result = await processor.process(agent_run=run, user_message="Two invalid turns")

        # Assert: Should fail after exactly 2 invalid turns
        assert run.status == AgentRunStatus.FAILED
        assert provider.call_count == 2  # Only 2 LLM calls before termination
        assert TOOL_CALLING_FAILURE_PREFIX in result
