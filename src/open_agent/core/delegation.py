"""DelegationManager: validates and routes delegation to child SessionProcessors."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent.agents.registry import AgentRegistry
from open_agent.bus import EventBus
from open_agent.persistence.models import AgentRun, AgentRunStatus, utcnow
from open_agent.persistence.store import Store

if TYPE_CHECKING:
    from open_agent.core.session import SessionProcessor

logger = logging.getLogger(__name__)


class DelegationError(Exception):
    pass


class DelegationManager:
    """Manages task delegation between agents.

    Validates delegation is allowed, checks depth limits,
    creates child AgentRuns, and spawns child SessionProcessors.
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        bus: EventBus,
        store: Store,
        max_depth: int = 3,
        session_processor_factory: Any = None,
    ) -> None:
        self.agent_registry = agent_registry
        self.bus = bus
        self.store = store
        self.max_depth = max_depth
        self._session_processor_factory = session_processor_factory

    def set_processor_factory(self, factory: Any) -> None:
        """Set the factory for creating child SessionProcessors.

        This is set after initialization to break the circular dependency
        between DelegationManager and SessionProcessor.
        """
        self._session_processor_factory = factory

    async def delegate(
        self,
        from_run: AgentRun,
        target_role: str,
        description: str,
    ) -> str:
        """Delegate a task from one agent to another.

        Creates a child AgentRun, spawns a child SessionProcessor,
        and returns the result.
        """
        # Validate target agent exists
        target_agent = self.agent_registry.get(target_role)
        if target_agent is None:
            raise DelegationError(f"No agent registered for role: {target_role}")

        # Check depth
        depth = await self._get_depth(from_run)
        if depth >= self.max_depth:
            raise DelegationError(
                f"Maximum delegation depth ({self.max_depth}) reached. Cannot delegate further."
            )

        # Create child run
        child_run = AgentRun(
            session_id=from_run.session_id,
            parent_run_id=from_run.id,
            agent_role=target_role,
            status=AgentRunStatus.RUNNING,
            description=description,
        )
        await self.store.create_agent_run(child_run)

        # Create child processor
        if self._session_processor_factory is None:
            raise DelegationError("No session processor factory configured")

        child_processor: SessionProcessor = self._session_processor_factory(
            agent=target_agent,
            parent_run=from_run,
        )

        # Run the child
        try:
            result = await child_processor.process(
                agent_run=child_run,
                user_message=description,
            )
        except Exception as e:
            child_run.status = AgentRunStatus.FAILED
            child_run.result = str(e)
            child_run.completed_at = utcnow()
            await self.store.update_agent_run(child_run)
            raise DelegationError(f"Child agent '{target_role}' failed: {e}") from e

        return result

    async def _get_depth(self, run: AgentRun) -> int:
        """Count how deep we are in the delegation chain."""
        depth = 0
        current = run
        while current.parent_run_id:
            depth += 1
            parent = await self.store.get_agent_run(current.parent_run_id)
            if parent is None:
                break
            current = parent
        return depth
