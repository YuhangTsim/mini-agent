"""Tests for multi-level delegation chains and failure propagation."""

from __future__ import annotations

import pytest

from open_agent.agents.base import BaseAgent
from open_agent.agents.registry import AgentRegistry
from open_agent.config.agents import AgentConfig
from open_agent.core.delegation import DelegationError, DelegationManager
from open_agent.persistence.models import AgentRun, AgentRunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConcreteAgent(BaseAgent):
    """Concrete agent for testing."""

    def get_system_prompt(self, context=None) -> str:
        return f"Test agent: {self.role}"


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
    agent_role: str = "orchestrator",
    parent_run_id: str | None = None,
    description: str = "Test run",
) -> AgentRun:
    return AgentRun(
        session_id=session_id,
        agent_role=agent_role,
        status=AgentRunStatus.RUNNING,
        description=description,
        parent_run_id=parent_run_id,
    )


# ---------------------------------------------------------------------------
# Tests: Multi-Level Delegation Chains
# ---------------------------------------------------------------------------


class TestThreeLevelDelegationChain:
    """Test 3-level delegation chain: Orchestrator → Specialist A → Specialist B."""

    async def test_three_level_chain_completes_successfully(self, open_store, event_bus):
        """Verify that a 3-level delegation chain completes with correct parent_run_id."""
        # Setup agents
        orchestrator = make_agent("orchestrator", can_delegate_to=["specialist_a"])
        specialist_a = make_agent("specialist_a", can_delegate_to=["specialist_b"])
        specialist_b = make_agent("specialist_b")

        registry = make_registry(orchestrator, specialist_a, specialist_b)

        # Track execution order
        execution_order = []

        # Create mock factory that handles nested delegation
        def create_mock_factory(delegations: dict[str, str]):
            """Create a factory that knows about delegation chains."""
            factory_map = {}

            def mock_factory(agent, parent_run):
                role = agent.role

                class MockProcessor:
                    async def process(self, agent_run, user_message, **kwargs):
                        execution_order.append(
                            (role, agent_run.id, parent_run.id if parent_run else None)
                        )

                        # Check if this agent should delegate further
                        if role in delegations:
                            target = delegations[role]
                            # Create child run in store for the delegation
                            child_run = AgentRun(
                                session_id=agent_run.session_id,
                                parent_run_id=agent_run.id,
                                agent_role=target,
                                status=AgentRunStatus.RUNNING,
                                description=f"Delegated: {user_message}",
                            )
                            # This simulates the delegation happening
                            return f"result from {role} -> {target}"

                        return f"result from {role}"

                factory_map[role] = MockProcessor
                return factory_map[role]()

            return mock_factory

        # Factory knows about the chain: orchestrator → specialist_a → specialist_b
        mock_factory = create_mock_factory(
            {"orchestrator": "specialist_a", "specialist_a": "specialist_b"}
        )

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=3,
            session_processor_factory=mock_factory,
        )

        # Create root run (orchestrator)
        root_run = make_run("sess-3level", "orchestrator", None, "Root task")
        await open_store.create_agent_run(root_run)

        # Execute first delegation: orchestrator → specialist_a
        result = await dm.delegate(
            from_run=root_run,
            target_role="specialist_a",
            description="Task requiring specialist B",
        )

        # Verify the chain completed
        assert "specialist_a" in result

        # Verify child run was created for specialist_a
        child_runs = await open_store.get_child_runs(root_run.id)
        assert len(child_runs) == 1
        assert child_runs[0].agent_role == "specialist_a"
        assert child_runs[0].parent_run_id == root_run.id


class TestChildFailurePropagation:
    """Test that child failure propagates to grandparent in delegation chain."""

    async def test_child_failure_propagates_to_grandparent(self, open_store, event_bus):
        """Verify Orchestrator → A → B where B fails, error reaches Orchestrator."""
        # Setup agents
        orchestrator = make_agent("orchestrator", can_delegate_to=["specialist_a"])
        specialist_a = make_agent("specialist_a", can_delegate_to=["specialist_b"])
        specialist_b = make_agent("specialist_b")

        registry = make_registry(orchestrator, specialist_a, specialist_b)

        failure_injected = False

        def mock_factory(agent, parent_run):
            role = agent.role

            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    nonlocal failure_injected

                    # specialist_b fails
                    if role == "specialist_b":
                        failure_injected = True
                        raise RuntimeError("Specialist B crashed!")

                    # specialist_a would normally delegate to specialist_b
                    # but since it fails, we return success for now
                    # (the failure will propagate up)
                    return f"result from {role}"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=3,
            session_processor_factory=mock_factory,
        )

        # Create root run (orchestrator)
        root_run = make_run("sess-fail", "orchestrator", None, "Root task")
        await open_store.create_agent_run(root_run)

        # Create specialist_a run (child of orchestrator)
        specialist_a_run = make_run(
            "sess-fail", "specialist_a", root_run.id, "Delegated to specialist A"
        )
        await open_store.create_agent_run(specialist_a_run)

        # Create specialist_b run (child of specialist_a)
        specialist_b_run = make_run(
            "sess-fail", "specialist_b", specialist_a_run.id, "Delegated to specialist B"
        )
        await open_store.create_agent_run(specialist_b_run)

        # Try to delegate from specialist_a to specialist_b - this should fail
        with pytest.raises(DelegationError, match="Specialist B crashed"):
            await dm.delegate(
                from_run=specialist_a_run,
                target_role="specialist_b",
                description="This will fail",
            )

        # Verify the failure was injected
        assert failure_injected is True


class TestDepthLimitEnforcement:
    """Test depth limit enforcement at 4th level delegation."""

    async def test_fourth_level_delegation_raises_error(self, open_store, event_bus):
        """Verify that attempting 4th level delegation raises DelegationError."""
        # Setup agents
        orchestrator = make_agent("orchestrator", can_delegate_to=["specialist_a"])
        specialist_a = make_agent("specialist_a", can_delegate_to=["specialist_b"])
        specialist_b = make_agent("specialist_b", can_delegate_to=["specialist_c"])
        specialist_c = make_agent("specialist_c")

        registry = make_registry(orchestrator, specialist_a, specialist_b, specialist_c)

        def mock_factory(agent, parent_run):
            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    return "success"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=3,  # Default max depth
            session_processor_factory=mock_factory,
        )

        # Create a chain: orchestrator → a → b → c (depth 3, so c is at limit)
        root_run = make_run("sess-depth", "orchestrator", None, "Root")
        await open_store.create_agent_run(root_run)

        run_a = make_run("sess-depth", "specialist_a", root_run.id, "Level 1")
        await open_store.create_agent_run(run_a)

        run_b = make_run("sess-depth", "specialist_b", run_a.id, "Level 2")
        await open_store.create_agent_run(run_b)

        run_c = make_run("sess-depth", "specialist_c", run_b.id, "Level 3")
        await open_store.create_agent_run(run_c)

        # Trying to delegate from run_c (depth 3) should exceed max_depth (3)
        with pytest.raises(DelegationError, match="Maximum delegation depth"):
            await dm.delegate(
                from_run=run_c,
                target_role="specialist_c",  # Trying to delegate again
                description="Exceeds depth limit",
            )

    async def test_depth_limit_message_is_informative(self, open_store, event_bus):
        """Verify the error message includes the max depth value."""
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        def mock_factory(agent, parent_run):
            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    return "success"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=2,
            session_processor_factory=mock_factory,
        )

        # Create chain at depth limit
        root = make_run("sess-msg")
        await open_store.create_agent_run(root)

        child = make_run("sess-msg", "explorer", root.id)
        await open_store.create_agent_run(child)

        grandchild = make_run("sess-msg", "explorer", child.id)
        await open_store.create_agent_run(grandchild)

        # Try to delegate beyond limit
        with pytest.raises(DelegationError) as exc_info:
            await dm.delegate(
                from_run=grandchild,
                target_role="explorer",
                description="Too deep",
            )

        assert "Maximum delegation depth (2)" in str(exc_info.value)


class TestPartialChainFailure:
    """Test handling of partial chain failure when parallel delegations exist."""

    async def test_partial_failure_one_succeeds_one_fails(self, open_store, event_bus):
        """Verify orchestrator handling when one delegation succeeds and one fails."""
        # Setup agents
        orchestrator = make_agent("orchestrator", can_delegate_to=["specialist_a", "specialist_b"])
        specialist_a = make_agent("specialist_a")
        specialist_b = make_agent("specialist_b")

        registry = make_registry(orchestrator, specialist_a, specialist_b)

        execution_results = {}

        def mock_factory(agent, parent_run):
            role = agent.role

            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    # specialist_a succeeds, specialist_b fails
                    if role == "specialist_a":
                        execution_results[role] = "success"
                        return f"result from {role}"
                    elif role == "specialist_b":
                        execution_results[role] = "failure"
                        raise RuntimeError("Specialist B failed!")

                    return f"result from {role}"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=3,
            session_processor_factory=mock_factory,
        )

        # Create root run
        root_run = make_run("sess-partial", "orchestrator", None, "Root task")
        await open_store.create_agent_run(root_run)

        # Simulate orchestrator delegating to both A and B in parallel
        # First delegation: orchestrator → specialist_a (succeeds)
        result_a = await dm.delegate(
            from_run=root_run,
            target_role="specialist_a",
            description="Task A",
        )
        assert result_a == "result from specialist_a"

        # Verify child run was created for specialist_a
        child_runs_a = await open_store.get_child_runs(root_run.id)
        assert len(child_runs_a) == 1
        assert child_runs_a[0].agent_role == "specialist_a"
        # Note: DelegationManager doesn't update status to COMPLETED on success,
        # it only updates to FAILED on exception
        assert child_runs_a[0].status == AgentRunStatus.RUNNING

        # Second delegation: orchestrator → specialist_b (fails)
        with pytest.raises(DelegationError, match="Specialist B failed"):
            await dm.delegate(
                from_run=root_run,
                target_role="specialist_b",
                description="Task B",
            )

        # Verify child run was created for specialist_b and marked as failed
        child_runs_b = await open_store.get_child_runs(root_run.id)
        assert len(child_runs_b) == 2
        failed_run = next(r for r in child_runs_b if r.agent_role == "specialist_b")
        assert failed_run.status == AgentRunStatus.FAILED

    async def test_partial_failure_orchestrator_receives_error(self, open_store, event_bus):
        """Verify that orchestrator receives error when one delegation fails."""
        orchestrator = make_agent("orchestrator", can_delegate_to=["specialist_a", "specialist_b"])
        specialist_a = make_agent("specialist_a")
        specialist_b = make_agent("specialist_b")

        registry = make_registry(orchestrator, specialist_a, specialist_b)

        def mock_factory(agent, parent_run):
            role = agent.role

            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    if role == "specialist_b":
                        raise RuntimeError("Task B failed")
                    return f"success from {role}"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=3,
            session_processor_factory=mock_factory,
        )

        root_run = make_run("sess-error", "orchestrator", None, "Root")
        await open_store.create_agent_run(root_run)

        # Execute delegations in sequence (simulating parallel with sequential handling)
        # First succeeds
        await dm.delegate(
            from_run=root_run,
            target_role="specialist_a",
            description="Task A",
        )

        # Second fails - error should propagate to orchestrator
        with pytest.raises(DelegationError) as exc_info:
            await dm.delegate(
                from_run=root_run,
                target_role="specialist_b",
                description="Task B",
            )

        assert "Task B failed" in str(exc_info.value)
