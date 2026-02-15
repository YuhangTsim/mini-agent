"""Typed async event bus — the backbone of Open-Agent."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable

from open_agent.bus.events import Event, EventPayload

logger = logging.getLogger(__name__)

Handler = Callable[[EventPayload], Awaitable[None]]


class EventBus:
    """Async pub/sub event bus with handler-based subscriptions and queue-based streams.

    Usage::

        bus = EventBus()

        # Handler-based
        async def on_token(payload: EventPayload):
            print(payload.data["token"])

        bus.subscribe(Event.TOKEN_STREAM, on_token)
        await bus.publish(Event.TOKEN_STREAM, session_id="s1", agent_role="coder", data={"token": "hi"})

        # Queue-based (for SSE streaming)
        queue = bus.stream(Event.TOKEN_STREAM)
        payload = await queue.get()
    """

    def __init__(self) -> None:
        self._handlers: dict[Event, list[Handler]] = defaultdict(list)
        self._wildcard_handlers: list[Handler] = []
        self._streams: dict[Event | None, list[asyncio.Queue[EventPayload]]] = defaultdict(list)

    def subscribe(self, event: Event | None, handler: Handler) -> Callable[[], None]:
        """Register an async handler for an event type.

        If event is None, the handler receives all events (wildcard).
        Returns an unsubscribe function.
        """
        if event is None:
            self._wildcard_handlers.append(handler)
            return lambda: self._wildcard_handlers.remove(handler)
        else:
            self._handlers[event].append(handler)
            return lambda: self._handlers[event].remove(handler)

    def stream(self, event: Event | None = None) -> asyncio.Queue[EventPayload]:
        """Return an asyncio.Queue that receives payloads for the given event.

        If event is None, the queue receives all events (wildcard).
        """
        queue: asyncio.Queue[EventPayload] = asyncio.Queue()
        self._streams[event].append(queue)
        return queue

    def unstream(self, queue: asyncio.Queue[EventPayload], event: Event | None = None) -> None:
        """Remove a previously created stream queue."""
        queues = self._streams.get(event, [])
        if queue in queues:
            queues.remove(queue)

    async def publish(
        self,
        event: Event,
        *,
        session_id: str,
        agent_role: str,
        data: dict | None = None,
        parent_session_id: str | None = None,
    ) -> None:
        """Publish an event to all matching handlers and stream queues."""
        payload = EventPayload(
            event=event,
            session_id=session_id,
            agent_role=agent_role,
            data=data or {},
            parent_session_id=parent_session_id,
        )

        # Fire handlers for this specific event
        for handler in self._handlers.get(event, []):
            try:
                await handler(payload)
            except Exception:
                logger.exception("Handler error for %s", event)

        # Fire wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                await handler(payload)
            except Exception:
                logger.exception("Wildcard handler error for %s", event)

        # Push to event-specific stream queues
        for queue in self._streams.get(event, []):
            queue.put_nowait(payload)

        # Push to wildcard stream queues
        if event is not None:
            for queue in self._streams.get(None, []):
                queue.put_nowait(payload)

    def clear(self) -> None:
        """Remove all handlers and streams."""
        self._handlers.clear()
        self._wildcard_handlers.clear()
        self._streams.clear()
