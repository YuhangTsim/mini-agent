"""Data models for sessions, agent runs, messages, and tool calls."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from mini_agent.persistence.models import (  # noqa: F401
    MessageRole,
    TokenUsage,
    new_id,
    utcnow,
)


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Session:
    """Top-level user interaction session."""

    id: str = field(default_factory=new_id)
    status: SessionStatus = SessionStatus.ACTIVE
    title: str = ""
    working_directory: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status.value,
            "title": self.title,
            "working_directory": self.working_directory,
            "metadata": json.dumps(self.metadata),
            "input_tokens": self.token_usage.input_tokens,
            "output_tokens": self.token_usage.output_tokens,
            "estimated_cost": self.token_usage.total_cost,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Session:
        return cls(
            id=row["id"],
            status=SessionStatus(row["status"]),
            title=row.get("title", ""),
            working_directory=row.get("working_directory", ""),
            metadata=json.loads(row.get("metadata") or "{}"),
            token_usage=TokenUsage(
                input_tokens=row.get("input_tokens", 0),
                output_tokens=row.get("output_tokens", 0),
                total_cost=row.get("estimated_cost", 0.0),
            ),
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"])
            if row.get("updated_at")
            else utcnow(),
        )


@dataclass
class AgentRun:
    """A single agent's execution within a session (or as a delegated child)."""

    id: str = field(default_factory=new_id)
    session_id: str = ""
    parent_run_id: str | None = None
    agent_role: str = ""
    status: AgentRunStatus = AgentRunStatus.RUNNING
    description: str = ""
    result: str | None = None
    is_background: bool = False
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    created_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "parent_run_id": self.parent_run_id,
            "agent_role": self.agent_role,
            "status": self.status.value,
            "description": self.description,
            "result": self.result,
            "is_background": int(self.is_background),
            "input_tokens": self.token_usage.input_tokens,
            "output_tokens": self.token_usage.output_tokens,
            "estimated_cost": self.token_usage.total_cost,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> AgentRun:
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            parent_run_id=row.get("parent_run_id"),
            agent_role=row["agent_role"],
            status=AgentRunStatus(row["status"]),
            description=row.get("description", ""),
            result=row.get("result"),
            is_background=bool(row.get("is_background", 0)),
            token_usage=TokenUsage(
                input_tokens=row.get("input_tokens", 0),
                output_tokens=row.get("output_tokens", 0),
                total_cost=row.get("estimated_cost", 0.0),
            ),
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row.get("completed_at")
            else None,
        )


@dataclass
class Message:
    id: str = field(default_factory=new_id)
    agent_run_id: str = ""
    role: MessageRole = MessageRole.USER
    content: str = ""
    token_count: int = 0
    is_compaction: bool = False  # Marks this as a compaction message
    summary: str | None = None  # Summary content for compaction messages
    created_at: datetime = field(default_factory=utcnow)

    @staticmethod
    def from_text(agent_run_id: str, role: MessageRole, text: str) -> Message:
        return Message(agent_run_id=agent_run_id, role=role, content=text)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "role": self.role.value,
            "content": self.content,
            "token_count": self.token_count,
            "is_compaction": int(self.is_compaction),
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Message:
        return cls(
            id=row["id"],
            agent_run_id=row["agent_run_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            token_count=row.get("token_count", 0),
            is_compaction=bool(row.get("is_compaction", 0)),
            summary=row.get("summary"),
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
        )


@dataclass
class SessionMessage:
    """Replayable session-level transcript entry for multi-turn context."""

    id: str = field(default_factory=new_id)
    session_id: str = ""
    sequence: int = 0
    source_run_id: str | None = None
    agent_role: str = ""
    role: MessageRole = MessageRole.USER
    kind: str = "message"
    content: str = ""
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime = field(default_factory=utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "source_run_id": self.source_run_id,
            "agent_role": self.agent_role,
            "role": self.role.value,
            "kind": self.kind,
            "content": self.content,
            "tool_call_id": self.tool_call_id,
            "tool_calls": json.dumps(self.tool_calls) if self.tool_calls is not None else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> SessionMessage:
        tool_calls = row.get("tool_calls")
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            sequence=row["sequence"],
            source_run_id=row.get("source_run_id"),
            agent_role=row.get("agent_role", ""),
            role=MessageRole(row["role"]),
            kind=row.get("kind", "message"),
            content=row.get("content", ""),
            tool_call_id=row.get("tool_call_id"),
            tool_calls=json.loads(tool_calls) if tool_calls else None,
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
        )

    def to_provider_dict(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": self.role.value}

        if self.role == MessageRole.TOOL:
            message["tool_call_id"] = self.tool_call_id or ""
            message["content"] = self.content
            return message

        if self.tool_calls:
            message["content"] = self.content or None
            message["tool_calls"] = self.tool_calls
            return message

        message["content"] = self.content
        return message


@dataclass
class MessagePart:
    """A part of a message with specific type for fine-grained compaction."""

    id: str = field(default_factory=new_id)
    message_id: str = ""
    part_type: str = ""  # "text", "file", "tool", "compaction", "subtask"
    content: str = ""
    tool_name: str | None = None
    tool_state: dict[str, Any] = field(default_factory=dict)  # status, output, etc.
    compacted_at: int | None = None  # timestamp when compacted
    created_at: datetime = field(default_factory=utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "part_type": self.part_type,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_state": json.dumps(self.tool_state),
            "compacted_at": self.compacted_at,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MessagePart:
        return cls(
            id=row["id"],
            message_id=row["message_id"],
            part_type=row["part_type"],
            content=row["content"],
            tool_name=row.get("tool_name"),
            tool_state=json.loads(row.get("tool_state") or "{}"),
            compacted_at=row.get("compacted_at"),
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
        )


@dataclass
class ToolCall:
    id: str = field(default_factory=new_id)
    agent_run_id: str = ""
    message_id: str | None = None
    tool_name: str = ""
    parameters: str = ""  # JSON
    result: str = ""  # JSON
    status: str = "success"  # success | error | denied
    duration_ms: int = 0
    created_at: datetime = field(default_factory=utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "message_id": self.message_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "result": self.result,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> ToolCall:
        return cls(
            id=row["id"],
            agent_run_id=row["agent_run_id"],
            message_id=row.get("message_id"),
            tool_name=row["tool_name"],
            parameters=row.get("parameters", ""),
            result=row.get("result", ""),
            status=row.get("status", "success"),
            duration_ms=row.get("duration_ms", 0),
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
        )


@dataclass
class TodoItem:
    """A todo item for tracking progress within a session."""

    id: str = field(default_factory=new_id)
    content: str = ""
    status: str = "pending"  # pending | in_progress | completed | cancelled
    priority: str = "medium"  # high | medium | low
    session_id: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> TodoItem:
        return cls(
            id=row["id"],
            content=row["content"],
            status=row["status"],
            priority=row["priority"],
            session_id=row["session_id"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"])
            if row.get("updated_at")
            else utcnow(),
        )
