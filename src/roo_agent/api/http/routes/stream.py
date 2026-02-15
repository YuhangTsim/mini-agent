"""Server-Sent Events (SSE) streaming endpoint."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from ...service import AgentService
from ..dependencies import get_service


router = APIRouter(prefix="/api/tasks/{task_id}", tags=["streaming"])


@router.get("/stream")
async def stream_events(
    task_id: str,
    service: AgentService = Depends(get_service),
):
    """Stream real-time events for a task via Server-Sent Events (SSE).

    Events include:
    - token_stream: LLM text streaming
    - tool_call_start: Tool execution started
    - tool_call_end: Tool execution completed
    - tool_approval_required: Tool needs user approval
    - user_input_required: Agent asking for user input
    - message_end: LLM response complete with token usage
    - task_status_changed: Task status updated
    """
    # Verify task exists
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    async def event_generator():
        """Generate SSE events from the EventBus."""
        # Subscribe to events for this task
        queue = service.event_bus.subscribe(task_id=task_id)

        try:
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({"task_id": task_id, "status": "connected"}),
            }

            # Stream events as they arrive
            while True:
                try:
                    # Wait for next event with timeout to allow checking connection
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Convert event to SSE format
                    yield {
                        "event": event.type.value,
                        "data": json.dumps(event.data),
                    }

                except asyncio.TimeoutError:
                    # Send keepalive ping every 30 seconds
                    yield {
                        "event": "ping",
                        "data": json.dumps({"timestamp": asyncio.get_event_loop().time()}),
                    }

        except asyncio.CancelledError:
            # Client disconnected
            service.event_bus.unsubscribe(queue, task_id=task_id)
            raise

        finally:
            # Clean up subscription
            service.event_bus.unsubscribe(queue, task_id=task_id)

    return EventSourceResponse(event_generator())
