"""Data models for tasks, messages, and tool calls."""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ContentBlock:
    type: str  # "text" | "image" | "file"
    text: str | None = None
    image_data: str | None = None  # base64
    mime_type: str | None = None
    file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.image_data is not None:
            d["image_data"] = self.image_data
        if self.mime_type is not None:
            d["mime_type"] = self.mime_type
        if self.file_path is not None:
            d["file_path"] = self.file_path
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentBlock:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0

    def add(self, other: TokenUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_cost += other.total_cost


@dataclass
class TodoItem:
    text: str
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "done": self.done}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TodoItem:
        return cls(text=data["text"], done=data.get("done", False))


@dataclass
class Task:
    id: str = field(default_factory=new_id)
    parent_id: str | None = None
    root_id: str | None = None
    mode: str = "code"
    status: TaskStatus = TaskStatus.PENDING
    title: str = ""
    description: str = ""
    working_directory: str = ""
    result: str | None = None
    todo_list: list[TodoItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    children: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    @property
    def pending_todos(self) -> list[TodoItem]:
        return [item for item in self.todo_list if not item.done]

    def to_row(self) -> dict[str, Any]:
        """Convert to a dict suitable for SQLite insertion."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "root_id": self.root_id,
            "mode": self.mode,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "working_directory": self.working_directory,
            "result": self.result,
            "todo_list": json.dumps([t.to_dict() for t in self.todo_list]),
            "metadata": json.dumps(self.metadata),
            "input_tokens": self.token_usage.input_tokens,
            "output_tokens": self.token_usage.output_tokens,
            "estimated_cost": self.token_usage.total_cost,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Task:
        todo_raw = json.loads(row.get("todo_list") or "[]")
        metadata = json.loads(row.get("metadata") or "{}")
        return cls(
            id=row["id"],
            parent_id=row.get("parent_id"),
            root_id=row.get("root_id"),
            mode=row["mode"],
            status=TaskStatus(row["status"]),
            title=row.get("title", ""),
            description=row.get("description", ""),
            working_directory=row.get("working_directory", ""),
            result=row.get("result"),
            todo_list=[TodoItem.from_dict(t) for t in todo_raw],
            metadata=metadata,
            token_usage=TokenUsage(
                input_tokens=row.get("input_tokens", 0),
                output_tokens=row.get("output_tokens", 0),
                total_cost=row.get("estimated_cost", 0.0),
            ),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
        )


@dataclass
class Message:
    id: str = field(default_factory=new_id)
    task_id: str = ""
    role: MessageRole = MessageRole.USER
    content: str = ""  # JSON string for multimodal, plain text for simple
    token_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def get_content_blocks(self) -> list[ContentBlock]:
        """Parse content as list of ContentBlocks."""
        try:
            data = json.loads(self.content)
            if isinstance(data, list):
                return [ContentBlock.from_dict(b) for b in data]
        except (json.JSONDecodeError, TypeError):
            pass
        return [ContentBlock(type="text", text=self.content)]

    @staticmethod
    def from_text(task_id: str, role: MessageRole, text: str) -> Message:
        return Message(task_id=task_id, role=role, content=text)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "role": self.role.value,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Message:
        return cls(
            id=row["id"],
            task_id=row["task_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            token_count=row.get("token_count", 0),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
        )


@dataclass
class ToolCall:
    id: str = field(default_factory=new_id)
    task_id: str = ""
    message_id: str | None = None
    tool_name: str = ""
    parameters: str = ""  # JSON
    result: str = ""  # JSON
    status: str = "success"  # success | error | denied
    duration_ms: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
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
            task_id=row["task_id"],
            message_id=row.get("message_id"),
            tool_name=row["tool_name"],
            parameters=row.get("parameters", ""),
            result=row.get("result", ""),
            status=row.get("status", "success"),
            duration_ms=row.get("duration_ms", 0),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else datetime.utcnow(),
        )
