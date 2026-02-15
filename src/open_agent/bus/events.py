"""Event types and payload for the Open-Agent event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Event(str, Enum):
    """All event types in the system."""

    # Session lifecycle
    SESSION_START = "session.start"
    SESSION_END = "session.end"

    # Agent lifecycle
    AGENT_START = "agent.start"
    AGENT_END = "agent.end"

    # LLM streaming
    TOKEN_STREAM = "token.stream"
    RESPONSE_COMPLETE = "response.complete"

    # Tool lifecycle
    TOOL_CALL_START = "tool_call.start"
    TOOL_CALL_END = "tool_call.end"
    TOOL_APPROVAL_REQUIRED = "tool_call.approval_required"
    TOOL_APPROVAL_RESPONSE = "tool_call.approval_response"

    # Delegation
    DELEGATION_START = "delegation.start"
    DELEGATION_END = "delegation.end"

    # Background tasks
    BACKGROUND_TASK_QUEUED = "background.queued"
    BACKGROUND_TASK_COMPLETE = "background.complete"
    BACKGROUND_TASK_FAILED = "background.failed"

    # Errors
    ERROR = "error"


@dataclass
class EventPayload:
    """Payload attached to every event published on the bus."""

    event: Event
    session_id: str
    agent_role: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_session_id: str | None = None
