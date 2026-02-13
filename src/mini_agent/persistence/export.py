"""JSON export logic for tasks and conversations."""

from __future__ import annotations

from typing import Any

from .models import Task, Message, ToolCall
from .store import Store


async def export_task(store: Store, task_id: str, include_children: bool = False) -> dict[str, Any]:
    """Export a task with its conversation and tool calls as a dict."""
    task = await store.get_task(task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    messages = await store.get_messages(task_id)
    tool_calls = await store.get_tool_calls(task_id)

    result: dict[str, Any] = {
        "task": _task_to_dict(task),
        "conversation": [_message_to_dict(m) for m in messages],
        "tool_calls": [_tool_call_to_dict(tc) for tc in tool_calls],
    }

    if include_children:
        children = await store.get_children(task_id)
        result["task"]["children"] = []
        for child in children:
            child_export = await export_task(store, child.id, include_children=True)
            result["task"]["children"].append(child_export)

    return result


def _task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "parent_id": task.parent_id,
        "title": task.title,
        "status": task.status.value,
        "mode": task.mode,
        "working_directory": task.working_directory,
        "description": task.description,
        "result": task.result,
        "token_usage": {
            "input": task.token_usage.input_tokens,
            "output": task.token_usage.output_tokens,
            "cost_usd": task.token_usage.total_cost,
        },
        "todo_list": [{"text": t.text, "done": t.done} for t in task.todo_list],
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _message_to_dict(msg: Message) -> dict[str, Any]:
    return {
        "role": msg.role.value,
        "content": msg.content,
        "token_count": msg.token_count,
        "timestamp": msg.created_at.isoformat(),
    }


def _tool_call_to_dict(tc: ToolCall) -> dict[str, Any]:
    return {
        "tool": tc.tool_name,
        "params": tc.parameters,
        "result": tc.result,
        "status": tc.status,
        "duration_ms": tc.duration_ms,
        "timestamp": tc.created_at.isoformat(),
    }
