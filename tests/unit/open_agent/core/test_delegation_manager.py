"""Tests for open_agent.core.delegation.DelegationManager."""

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
    def get_system_prompt(self, context=None) -> str:
        return "Test agent prompt."


def make_agent(role: str, can_delegate_to: list[str] | None = None) -> ConcreteAgent:
    config = AgentConfig(role=role, can_delegate_to=can_delegate_to or [])
    return ConcreteAgent(config)


def make_registry(*agents) -> AgentRegistry:
    reg = AgentRegistry()
    for agent in agents:
        reg.register(agent)
    return reg


def make_run(session_id: str = "sess-1", parent_run_id: str | None = None) -> AgentRun:
    return AgentRun(
        session_id=session_id,
        agent_role="orchestrator",
        status=AgentRunStatus.RUNNING,
        description="Parent run",
        parent_run_id=parent_run_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDelegationManagerBasics:
    async def test_delegate_to_registered_agent(self, open_store, event_bus):
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        results = []

        def mock_factory(agent, parent_run):
            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    results.append((agent.role, user_message))
                    return f"result from {agent.role}"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        result = await dm.delegate(
            from_run=parent_run,
            target_role="explorer",
            description="Find all Python files",
        )

        assert result == "result from explorer"
        assert len(results) == 1
        assert results[0] == ("explorer", "Find all Python files")

    async def test_delegate_creates_child_agent_run(self, open_store, event_bus):
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        def mock_factory(agent, parent_run):
            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    return "explorer result"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        await dm.delegate(
            from_run=parent_run,
            target_role="explorer",
            description="Do exploration",
        )

        child_runs = await open_store.get_child_runs(parent_run.id)
        assert len(child_runs) == 1
        assert child_runs[0].agent_role == "explorer"
        assert child_runs[0].parent_run_id == parent_run.id

    async def test_delegate_unknown_agent_raises(self, open_store, event_bus):
        registry = make_registry()  # Empty registry

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=None,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        with pytest.raises(DelegationError, match="No agent registered"):
            await dm.delegate(
                from_run=parent_run,
                target_role="nonexistent",
                description="This will fail",
            )

    async def test_delegate_without_factory_raises(self, open_store, event_bus):
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            session_processor_factory=None,
        )

        parent_run = make_run()
        await open_store.create_agent_run(parent_run)

        with pytest.raises(DelegationError, match="No session processor factory"):
            await dm.delegate(
                from_run=parent_run,
                target_role="explorer",
                description="Need factory",
            )

    async def test_set_processor_factory(self, open_store, event_bus):
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        dm = DelegationManager(
            agent_registry=registry, bus=event_bus, store=open_store
        )
        assert dm._session_processor_factory is None

        async def factory(agent, parent_run):
            pass

        dm.set_processor_factory(factory)
        assert dm._session_processor_factory is factory


class TestDelegationDepthLimit:
    async def test_depth_limit_enforced(self, open_store, event_bus):
        explorer = make_agent("explorer")
        registry = make_registry(explorer)

        async def mock_factory(agent, parent_run):
            class MockProcessor:
                async def process(self, agent_run, user_message, **kwargs):
                    return "result"

            return MockProcessor()

        dm = DelegationManager(
            agent_registry=registry,
            bus=event_bus,
            store=open_store,
            max_depth=1,
            session_processor_factory=mock_factory,
        )

        # Create a chain: root → child (depth=1)
        root_run = make_run("sess-depth")
        await open_store.create_agent_run(root_run)

        child_run = AgentRun(
            session_id="sess-depth",
            agent_role="explorer",
            parent_run_id=root_run.id,
            status=AgentRunStatus.RUNNING,
            description="Child",
        )
        await open_store.create_agent_run(child_run)

        # Trying to delegate from child_run should exceed depth limit
        with pytest.raises(DelegationError, match="Maximum delegation depth"):
            await dm.delegate(
                from_run=child_run,
                target_role="explorer",
                description="Too deep",
            )

    async def test_within_depth_limit_succeeds(self, open_store, event_bus):
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
            max_depth=3,
            session_processor_factory=mock_factory,
        )

        parent_run = make_run("sess-ok")
        await open_store.create_agent_run(parent_run)

        result = await dm.delegate(
            from_run=parent_run,
            target_role="explorer",
            description="First delegation (depth=0)",
        )
        assert result == "success"


class TestDelegationErrorHandling:
    async def test_child_failure_raises_delegation_error(self, open_store, event_bus):
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

        with pytest.raises(DelegationError, match="Child agent 'explorer' failed"):
            await dm.delegate(
                from_run=parent_run,
                target_role="explorer",
                description="This will crash",
            )

    async def test_child_failure_marks_run_failed(self, open_store, event_bus):
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

        child_runs = await open_store.get_child_runs(parent_run.id)
        assert len(child_runs) == 1
        assert child_runs[0].status == AgentRunStatus.FAILED
