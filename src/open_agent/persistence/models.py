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
