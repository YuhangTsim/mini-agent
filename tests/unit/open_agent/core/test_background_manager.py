"""Tests for open_agent.core.background.BackgroundTaskManager."""

from __future__ import annotations

import asyncio

import pytest

from open_agent.core.background import BackgroundTask, BackgroundTaskManager
from open_agent.persistence.models import AgentRun, AgentRunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_run(session_id: str = "sess-1") -> AgentRun:
    return AgentRun(
        session_id=session_id,
        agent_role="orchestrator",
        status=AgentRunStatus.RUNNING,
        description="Parent run",
    )


class MockDelegationManager:
    def __init__(self, results: dict[str, str] | None = None, delay: float = 0.0):
        self._results = results or {}
        self._delay = delay
        self.calls: list[tuple] = []

    async def delegate(self, from_run, target_role, description):
        self.calls.append((target_role, description))
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if target_role in self._results:
            return self._results[target_role]
        return f"Result from {target_role}"


class FailingDelegationManager:
    async def delegate(self, from_run, target_role, description):
        raise RuntimeError(f"Agent {target_role} failed!")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBackgroundTaskManagerSubmit:
    async def test_submit_returns_task_id(self, open_store, event_bus):
        dm = MockDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Search")

        assert task_id is not None
        assert isinstance(task_id, str)
        assert len(task_id) > 0

    async def test_submit_returns_immediately(self, open_store, event_bus):
        """submit() should return before the task completes."""
        dm = MockDelegationManager(delay=1.0)  # Slow task
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        import time
        start = time.monotonic()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Slow")
        elapsed = time.monotonic() - start

        # Should return much faster than the 1 second delay
        assert elapsed < 0.5
        assert task_id is not None
        # Clean up background task
        manager._tasks[task_id].asyncio_task.cancel()

    async def test_task_tracked_in_manager(self, open_store, event_bus):
        dm = MockDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="fixer", description="Fix it")

        assert task_id in manager.all_tasks
        bg_task = manager.all_tasks[task_id]
        assert bg_task.target_role == "fixer"
        assert bg_task.description == "Fix it"

    async def test_multiple_tasks_tracked(self, open_store, event_bus):
        dm = MockDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        id1 = await manager.submit(from_run=run, target_role="explorer", description="Task 1")
        id2 = await manager.submit(from_run=run, target_role="fixer", description="Task 2")

        assert id1 != id2
        assert id1 in manager.all_tasks
        assert id2 in manager.all_tasks


class TestBackgroundTaskManagerStatus:
    async def test_status_running_before_completion(self, open_store, event_bus):
        dm = MockDelegationManager(delay=2.0)
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Slow")
        status = await manager.get_status(task_id)

        assert "still running" in status
        manager._tasks[task_id].asyncio_task.cancel()

    async def test_status_completed_after_task_done(self, open_store, event_bus):
        dm = MockDelegationManager(results={"explorer": "Found files"})
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Search")
        # Wait for completion
        await asyncio.sleep(0.1)

        status = await manager.get_status(task_id)
        assert "COMPLETED" in status
        assert "Found files" in status

    async def test_status_failed_after_error(self, open_store, event_bus):
        dm = FailingDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Will fail")
        await asyncio.sleep(0.1)

        status = await manager.get_status(task_id)
        assert "FAILED" in status

    async def test_status_unknown_task(self, open_store, event_bus):
        manager = BackgroundTaskManager(bus=event_bus, store=open_store)
        status = await manager.get_status("nonexistent-task-id")
        assert "Unknown" in status


class TestBackgroundTaskManagerConcurrency:
    async def test_semaphore_limits_concurrent_tasks(self, open_store, event_bus):
        """Tasks beyond max_concurrent should queue behind the semaphore."""
        running_count = 0
        max_seen = 0

        async def slow_delegate(from_run, target_role, description):
            nonlocal running_count, max_seen
            running_count += 1
            max_seen = max(max_seen, running_count)
            await asyncio.sleep(0.05)
            running_count -= 1
            return "done"

        class CountingDM:
            async def delegate(self, from_run, target_role, description):
                return await slow_delegate(from_run, target_role, description)

        manager = BackgroundTaskManager(
            bus=event_bus,
            store=open_store,
            delegation_manager=CountingDM(),
            max_concurrent=2,
        )

        run = make_run()
        tasks = [
            await manager.submit(from_run=run, target_role="explorer", description=f"Task {i}")
            for i in range(4)
        ]

        # Wait for all to complete
        await asyncio.sleep(0.5)

        assert max_seen <= 2, f"Semaphore not respected: saw {max_seen} concurrent tasks"


class TestBackgroundTaskManagerActiveCount:
    async def test_active_count_increases_on_submit(self, open_store, event_bus):
        dm = MockDelegationManager(delay=1.0)
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        assert manager.active_count == 0
        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Task")
        assert manager.active_count == 1
        manager._tasks[task_id].asyncio_task.cancel()

    async def test_active_count_decreases_on_completion(self, open_store, event_bus):
        dm = MockDelegationManager(results={"explorer": "done"})
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        await manager.submit(from_run=run, target_role="explorer", description="Task")
        await asyncio.sleep(0.1)  # Wait for completion

        assert manager.active_count == 0


class TestBackgroundTaskManagerCancel:
    async def test_cancel_running_task(self, open_store, event_bus):
        dm = MockDelegationManager(delay=5.0)
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Long task")
        cancelled = await manager.cancel(task_id)

        assert cancelled is True
        assert manager._tasks[task_id].is_complete
        assert manager._tasks[task_id].error == "Cancelled"

    async def test_cancel_completed_task_returns_false(self, open_store, event_bus):
        dm = MockDelegationManager(results={"explorer": "done"})
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(from_run=run, target_role="explorer", description="Fast")
        await asyncio.sleep(0.1)  # Wait for completion

        cancelled = await manager.cancel(task_id)
        assert cancelled is False

    async def test_cancel_unknown_task_returns_false(self, open_store, event_bus):
        manager = BackgroundTaskManager(bus=event_bus, store=open_store)
        cancelled = await manager.cancel("nonexistent")
        assert cancelled is False
