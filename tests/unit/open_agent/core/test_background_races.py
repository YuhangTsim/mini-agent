"""Tests for race conditions in background task management.

These tests verify that the BackgroundTaskManager handles concurrent
access and race conditions correctly:

1. Status check while task running - verify no race between status check and completion
2. Cancellation during execution - verify graceful cancellation with cleanup
3. Semaphore exhaustion - verify 4th task queued correctly when slots full
4. Task completion race - verify no errors when task completes between check and result
"""

from __future__ import annotations

import asyncio

import pytest

from open_agent.bus import EventBus
from open_agent.core.background import BackgroundTaskManager
from open_agent.persistence.models import AgentRun, AgentRunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Test 1: Status check while task running
# ---------------------------------------------------------------------------


class TestStatusCheckWhileRunning:
    """Test that status checks work correctly while task is running."""

    async def test_status_check_returns_still_running(self, open_store, event_bus):
        """Verify status shows 'still running' for in-progress background task."""

        class SlowDelegationManager:
            """Delegation manager that takes 2 seconds to complete."""

            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(2.0)
                return "Task completed slowly"

        dm = SlowDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()

        # Submit a long-running task
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Long running task",
        )

        # Check status immediately - should show "still running"
        status = await manager.get_status(task_id)
        assert "still running" in status
        assert task_id in status

        # Wait for task to complete
        await asyncio.sleep(2.5)

        # Now status should show completed
        status = await manager.get_status(task_id)
        assert "COMPLETED" in status
        assert "Task completed slowly" in status

    async def test_no_race_between_status_check_and_completion(self, open_store, event_bus):
        """Verify no race condition between status check and task completion."""
        completed = asyncio.Event()
        check_count = 0

        class FastThenSlowDelegationManager:
            """Simulates a task that appears to complete quickly but takes longer."""

            async def delegate(self, from_run, target_role, description):
                # Signal we've been called
                completed.set()
                # Actually take time to complete
                await asyncio.sleep(0.5)
                return "Done"

        dm = FastThenSlowDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Fast then slow task",
        )

        # Wait for the delegation to start
        await completed.wait()

        # Quickly check status multiple times while task is running
        for _ in range(5):
            status = await manager.get_status(task_id)
            check_count += 1
            # Should always show still running
            assert "still running" in status
            await asyncio.sleep(0.05)

        # Wait for actual completion
        await asyncio.sleep(0.6)

        # Final status should show completed
        status = await manager.get_status(task_id)
        assert "COMPLETED" in status
        # Verify we did multiple checks
        assert check_count == 5


# ---------------------------------------------------------------------------
# Test 2: Cancellation during execution
# ---------------------------------------------------------------------------


class TestCancellationDuringExecution:
    """Test that cancellation works correctly during task execution."""

    async def test_cancel_while_running_graceful(self, open_store, event_bus):
        """Verify graceful cancellation of running task."""

        class CancellableDelegationManager:
            """A delegation that can be interrupted."""

            async def delegate(self, from_run, target_role, description):
                try:
                    await asyncio.sleep(5.0)  # Long running task
                    return "Should not reach here"
                except asyncio.CancelledError:
                    # Clean up any resources here if needed
                    raise

        dm = CancellableDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Cancellable task",
        )

        # Give task time to start
        await asyncio.sleep(0.1)

        # Cancel the task
        cancelled = await manager.cancel(task_id)
        assert cancelled is True

        # Verify status shows cancelled
        status = await manager.get_status(task_id)
        assert "CANCELLED" in status or "Cancelled" in status

        # Verify task is marked complete
        bg_task = manager.all_tasks[task_id]
        assert bg_task.is_complete is True

    async def test_cancel_cleanup_resources(self, open_store, event_bus):
        """Verify resources are cleaned up after cancellation."""

        class ResourceDelegationManager:
            """Tracks cleanup calls."""

            cleanup_called = False

            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(10.0)
                return "Done"

        dm = ResourceDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Resource task",
        )

        # Wait for start
        await asyncio.sleep(0.1)

        # Verify task is tracked
        assert task_id in manager.all_tasks

        # Cancel
        await manager.cancel(task_id)

        # Task should still be in the dict (for debugging) but marked complete
        bg_task = manager.all_tasks[task_id]
        assert bg_task.is_complete is True
        assert bg_task.error == "Cancelled"

    async def test_cancel_completed_task_returns_false(self, open_store, event_bus):
        """Verify cancelling a completed task returns False."""

        class FastDelegationManager:
            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(0.1)
                return "Done"

        dm = FastDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Quick task",
        )

        # Wait for completion
        await asyncio.sleep(0.2)

        # Try to cancel - should fail
        cancelled = await manager.cancel(task_id)
        assert cancelled is False


# ---------------------------------------------------------------------------
# Test 3: Semaphore exhaustion
# ---------------------------------------------------------------------------


class TestSemaphoreExhaustion:
    """Test behavior when semaphore slots are exhausted."""

    async def test_fourth_task_queued_when_slots_full(self, open_store, event_bus):
        """Verify 4th task is queued correctly when 3 slots are full."""

        # Track which tasks complete
        completed_tasks: asyncio.Queue = asyncio.Queue()

        class BlockingDelegationManager:
            """A delegation that blocks for a while."""

            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(2.0)  # Hold the slot
                await completed_tasks.put(target_role)
                return f"Done: {target_role}"

        dm = BlockingDelegationManager()
        # Use max_concurrent=3
        manager = BackgroundTaskManager(
            bus=event_bus,
            store=open_store,
            delegation_manager=dm,
            max_concurrent=3,
        )

        run = make_run()

        # Submit 3 tasks that will block (they will hold semaphore slots)
        task_ids = []
        for i in range(3):
            task_id = await manager.submit(
                from_run=run,
                target_role=f"agent-{i}",
                description=f"Blocking task {i}",
            )
            task_ids.append(task_id)

        # Small delay to let tasks start
        await asyncio.sleep(0.1)

        # Submit 4th task - it will wait for semaphore
        fourth_task_id = await manager.submit(
            from_run=run,
            target_role="agent-3",
            description="Fourth task",
        )

        # Wait for all 4 to complete (semaphore will queue the 4th)
        completed = []
        while len(completed) < 4:
            try:
                role = await asyncio.wait_for(completed_tasks.get(), timeout=5.0)
                completed.append(role)
            except asyncio.TimeoutError:
                break

        # All 4 should have completed - the 4th was queued by the semaphore
        assert len(completed) == 4

        # Verify all tasks completed successfully
        for task_id in task_ids + [fourth_task_id]:
            status = await manager.get_status(task_id)
            assert "COMPLETED" in status

    async def test_active_count_respects_completion(self, open_store, event_bus):
        """Verify active_count decreases as tasks complete."""

        completion_events: asyncio.Queue = asyncio.Queue()

        class TrackingDelegationManager:
            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(0.2)
                await completion_events.put(target_role)
                return "Done"

        dm = TrackingDelegationManager()
        manager = BackgroundTaskManager(
            bus=event_bus,
            store=open_store,
            delegation_manager=dm,
            max_concurrent=2,
        )

        run = make_run()

        # Submit 2 tasks
        task1 = await manager.submit(
            from_run=run,
            target_role="agent-1",
            description="Task 1",
        )
        task2 = await manager.submit(
            from_run=run,
            target_role="agent-2",
            description="Task 2",
        )

        # Both should be active (not complete yet)
        assert manager.active_count == 2

        # Wait for one to complete - wait for the queue to have an item
        try:
            await asyncio.wait_for(completion_events.get(), timeout=0.5)
        except asyncio.TimeoutError:
            pass

        # Small delay to ensure state is updated
        await asyncio.sleep(0.05)

        # Should be 0 now (both completed in quick succession)
        # or could be 1 if one completed before the other started
        assert manager.active_count in [0, 1]

        # Wait for second to complete
        await asyncio.sleep(0.3)

        # Should be 0
        assert manager.active_count == 0


# ---------------------------------------------------------------------------
# Test 4: Task completion race
# ---------------------------------------------------------------------------


class TestTaskCompletionRace:
    """Test race conditions around task completion."""

    async def test_no_error_checking_status_after_completion(self, open_store, event_bus):
        """Verify no errors when checking status after task completes."""

        class QuickDelegationManager:
            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(0.05)
                return "Quick result"

        dm = QuickDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Quick task",
        )

        # Poll status until complete
        for _ in range(20):
            status = await manager.get_status(task_id)
            # Should not raise any errors
            assert status is not None
            if "COMPLETED" in status:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("Task did not complete in expected time")

        # Verify final result
        status = await manager.get_status(task_id)
        assert "Quick result" in status

    async def test_result_returned_correctly_after_completion(self, open_store, event_bus):
        """Verify result is correctly returned after task completes."""

        expected_result = "Task completed with specific result data"

        class ResultDelegationManager:
            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(0.1)
                return expected_result

        dm = ResultDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Result task",
        )

        # Wait for completion
        await asyncio.sleep(0.2)

        # Verify result in the task object
        bg_task = manager.all_tasks[task_id]
        assert bg_task.result == expected_result
        assert bg_task.is_complete is True

    async def test_concurrent_status_checks_all_succeed(self, open_store, event_bus):
        """Verify multiple concurrent status checks don't cause issues."""

        class VariableDelegationManager:
            async def delegate(self, from_run, target_role, description):
                await asyncio.sleep(0.3)
                return "Done"

        dm = VariableDelegationManager()
        manager = BackgroundTaskManager(bus=event_bus, store=open_store, delegation_manager=dm)

        run = make_run()
        task_id = await manager.submit(
            from_run=run,
            target_role="explorer",
            description="Variable task",
        )

        # Launch multiple concurrent status checks
        async def check_status():
            return await manager.get_status(task_id)

        # Run 10 concurrent checks
        results = await asyncio.gather(*[check_status() for _ in range(10)])

        # All should succeed and have valid results
        for status in results:
            assert status is not None
            assert len(status) > 0
            # Some should show "still running", some "COMPLETED"
            assert ("still running" in status) or ("COMPLETED" in status)


# ---------------------------------------------------------------------------
# Integration test: All race conditions together
# ---------------------------------------------------------------------------


class TestRaceConditionIntegration:
    """Integration tests combining multiple race conditions."""

    async def test_mixed_operations_no_interference(self, open_store, event_bus):
        """Verify mixed operations don't interfere with each other."""

        task_completion_order = []

        class MixedDelegationManager:
            async def delegate(self, from_run, target_role, description):
                # Different delays for different tasks
                delay = float(description.split()[-1])  # Last word is delay
                await asyncio.sleep(delay)
                task_completion_order.append(target_role)
                return f"{target_role} done in {delay}s"

        dm = MixedDelegationManager()
        manager = BackgroundTaskManager(
            bus=event_bus,
            store=open_store,
            delegation_manager=dm,
            max_concurrent=2,
        )

        run = make_run()

        # Submit tasks with different durations
        t1 = await manager.submit(from_run=run, target_role="fast", description="Fast 0.1")
        t2 = await manager.submit(from_run=run, target_role="medium", description="Medium 0.3")
        t3 = await manager.submit(from_run=run, target_role="slow", description="Slow 0.5")

        # Wait for all to complete
        await asyncio.sleep(1.0)

        # Check all statuses
        status1 = await manager.get_status(t1)
        status2 = await manager.get_status(t2)
        status3 = await manager.get_status(t3)

        assert "COMPLETED" in status1
        assert "COMPLETED" in status2
        assert "COMPLETED" in status3

        # Fast should complete first
        assert task_completion_order[0] == "fast"
