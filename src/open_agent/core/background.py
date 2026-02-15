"""BackgroundTaskManager: fire-and-forget tasks with concurrency control."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from open_agent.bus import Event, EventBus
from open_agent.persistence.models import AgentRun
from open_agent.persistence.store import Store

logger = logging.getLogger(__name__)


@dataclass
class BackgroundTask:
    """Tracks a background task."""

    task_id: str
    agent_run_id: str
    target_role: str
    description: str
    asyncio_task: asyncio.Task | None = None
    result: str | None = None
    error: str | None = None
    is_complete: bool = False


class BackgroundTaskManager:
    """Manages fire-and-forget background delegations.

    Uses an asyncio.Semaphore to limit concurrent background tasks.
    """

    def __init__(
        self,
        bus: EventBus,
        store: Store,
        delegation_manager: Any = None,
        max_concurrent: int = 3,
    ) -> None:
        self.bus = bus
        self.store = store
        self._delegation_manager = delegation_manager
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, BackgroundTask] = {}

    def set_delegation_manager(self, dm: Any) -> None:
        self._delegation_manager = dm

    async def submit(
        self,
        from_run: AgentRun,
        target_role: str,
        description: str,
    ) -> str:
        """Submit a background task. Returns immediately with a task_id."""
        from open_agent.persistence.models import new_id

        task_id = new_id()

        bg_task = BackgroundTask(
            task_id=task_id,
            agent_run_id=from_run.id,
            target_role=target_role,
            description=description,
        )
        self._tasks[task_id] = bg_task

        await self.bus.publish(
            Event.BACKGROUND_TASK_QUEUED,
            session_id=from_run.session_id,
            agent_role=target_role,
            data={"task_id": task_id, "description": description},
        )

        # Start the background coroutine
        bg_task.asyncio_task = asyncio.create_task(self._run_background(bg_task, from_run))

        return task_id

    async def _run_background(self, bg_task: BackgroundTask, from_run: AgentRun) -> None:
        """Run a background delegation under semaphore control."""
        async with self._semaphore:
            try:
                result = await self._delegation_manager.delegate(
                    from_run=from_run,
                    target_role=bg_task.target_role,
                    description=bg_task.description,
                )
                bg_task.result = result
                bg_task.is_complete = True

                await self.bus.publish(
                    Event.BACKGROUND_TASK_COMPLETE,
                    session_id=from_run.session_id,
                    agent_role=bg_task.target_role,
                    data={"task_id": bg_task.task_id, "result": result[:200]},
                )
            except Exception as e:
                bg_task.error = str(e)
                bg_task.is_complete = True
                logger.exception("Background task %s failed", bg_task.task_id)

                await self.bus.publish(
                    Event.BACKGROUND_TASK_FAILED,
                    session_id=from_run.session_id,
                    agent_role=bg_task.target_role,
                    data={"task_id": bg_task.task_id, "error": str(e)},
                )

    async def get_status(self, task_id: str) -> str:
        """Get a human-readable status for a background task."""
        bg_task = self._tasks.get(task_id)
        if bg_task is None:
            return f"Unknown background task: {task_id}"

        if not bg_task.is_complete:
            return f"Background task {task_id} ({bg_task.target_role}): still running"

        if bg_task.error:
            return f"Background task {task_id} ({bg_task.target_role}): FAILED - {bg_task.error}"

        return (
            f"Background task {task_id} ({bg_task.target_role}): COMPLETED\n"
            f"Result: {bg_task.result}"
        )

    async def cancel(self, task_id: str) -> bool:
        """Cancel a background task if it's still running."""
        bg_task = self._tasks.get(task_id)
        if bg_task is None or bg_task.is_complete:
            return False
        if bg_task.asyncio_task and not bg_task.asyncio_task.done():
            bg_task.asyncio_task.cancel()
            bg_task.is_complete = True
            bg_task.error = "Cancelled"
            return True
        return False

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.is_complete)

    @property
    def all_tasks(self) -> dict[str, BackgroundTask]:
        return dict(self._tasks)
