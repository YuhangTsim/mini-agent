"""Task management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas import (
    ModeSwitch,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TodoItemResponse,
    TokenUsageResponse,
)
from ...service import AgentService
from ..dependencies import get_service


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_to_response(task) -> TaskResponse:
    """Convert Task model to TaskResponse schema."""
    return TaskResponse(
        id=task.id,
        parent_id=task.parent_id,
        root_id=task.root_id,
        mode=task.mode,
        status=task.status.value,
        title=task.title,
        description=task.description,
        working_directory=task.working_directory,
        created_at=task.created_at,
        updated_at=task.updated_at,
        token_usage=TokenUsageResponse(
            input_tokens=task.token_usage.input_tokens,
            output_tokens=task.token_usage.output_tokens,
        ),
        todo_list=[
            TodoItemResponse(text=item.text, done=item.done)
            for item in (task.todo_list or [])
        ],
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    service: AgentService = Depends(get_service),
) -> TaskResponse:
    """Create a new task."""
    try:
        task = await service.create_task(
            description=data.description,
            mode=data.mode,
            parent_id=data.parent_id,
            title=data.title,
        )
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    parent_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    service: AgentService = Depends(get_service),
) -> TaskListResponse:
    """List tasks."""
    tasks = await service.list_tasks(
        parent_id=parent_id,
        status=status_filter,
        limit=limit,
    )
    return TaskListResponse(
        tasks=[_task_to_response(task) for task in tasks]
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    service: AgentService = Depends(get_service),
) -> TaskResponse:
    """Get task details."""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )
    return _task_to_response(task)


@router.delete("/{task_id}", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    service: AgentService = Depends(get_service),
) -> TaskResponse:
    """Cancel a task."""
    try:
        task = await service.cancel_task(task_id)
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{task_id}/mode", response_model=TaskResponse)
async def switch_mode(
    task_id: str,
    data: ModeSwitch,
    service: AgentService = Depends(get_service),
) -> TaskResponse:
    """Switch task mode."""
    try:
        task = await service.switch_mode(task_id, data.mode)
        return _task_to_response(task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
