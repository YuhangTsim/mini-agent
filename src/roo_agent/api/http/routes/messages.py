"""Message endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from ..schemas import MessageCreate, MessageListResponse, MessageResponse
from ...service import AgentService
from ..dependencies import get_service


router = APIRouter(prefix="/api/tasks/{task_id}/messages", tags=["messages"])


def _message_to_response(message) -> MessageResponse:
    """Convert Message model to MessageResponse schema."""
    return MessageResponse(
        id=message.id,
        task_id=message.task_id,
        role=message.role.value,
        content=message.content,
        created_at=message.created_at,
        tool_calls=getattr(message, "tool_calls", None) or [],
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    task_id: str,
    data: MessageCreate,
    background_tasks: BackgroundTasks,
    service: AgentService = Depends(get_service),
) -> dict:
    """Send a message to the agent and trigger processing.

    The agent will process the message asynchronously and emit events
    via the EventBus. Listen to the /stream endpoint for real-time updates.
    """
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    # Start agent processing in background
    async def process_message():
        try:
            await service.send_message(task_id, data.content)
        except Exception as e:
            # Emit error to SSE stream so client can display it
            from ...events import Event, EventType
            await service.event_bus.emit(Event(
                type=EventType.MESSAGE_END,
                task_id=task_id,
                data={
                    "error": str(e),
                    "input_tokens": 0,
                    "output_tokens": 0,
                },
            ))

    background_tasks.add_task(process_message)

    return {
        "status": "accepted",
        "message": "Message queued for processing",
        "task_id": task_id,
    }


@router.get("", response_model=MessageListResponse)
async def get_messages(
    task_id: str,
    service: AgentService = Depends(get_service),
) -> MessageListResponse:
    """Get message history for a task."""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    messages = await service.get_messages(task_id)
    return MessageListResponse(
        messages=[_message_to_response(msg) for msg in messages]
    )
