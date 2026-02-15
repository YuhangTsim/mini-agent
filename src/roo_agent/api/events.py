"""Event bus for real-time updates."""

from __future__ import annotations

import asyncio
import enum
from dataclasses import dataclass, field
from typing import Any


class EventType(str, enum.Enum):
    TOKEN_STREAM = "token_stream"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_APPROVAL_REQUIRED = "tool_approval_required"
    TASK_STATUS_CHANGED = "task_status_changed"
    USER_INPUT_REQUIRED = "user_input_required"
    MESSAGE_ADDED = "message_added"
    MESSAGE_END = "message_end"


@dataclass
class Event:
    type: EventType
    task_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Simple async event bus with per-task subscriptions."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._global_subscribers: list[asyncio.Queue] = []

    async def emit(self, event: Event) -> None:
        """Emit an event to all subscribers."""
        # Task-specific subscribers
        if event.task_id and event.task_id in self._subscribers:
            for queue in self._subscribers[event.task_id]:
                await queue.put(event)

        # Global subscribers
        for queue in self._global_subscribers:
            await queue.put(event)

    def subscribe(self, task_id: str | None = None) -> asyncio.Queue:
        """Subscribe to events. Returns a queue that receives events."""
        queue: asyncio.Queue = asyncio.Queue()
        if task_id:
            if task_id not in self._subscribers:
                self._subscribers[task_id] = []
            self._subscribers[task_id].append(queue)
        else:
            self._global_subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue, task_id: str | None = None) -> None:
        """Remove a subscription."""
        if task_id and task_id in self._subscribers:
            try:
                self._subscribers[task_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]
        else:
            try:
                self._global_subscribers.remove(queue)
            except ValueError:
                pass
