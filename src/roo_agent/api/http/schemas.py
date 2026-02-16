"""Pydantic schemas for HTTP API request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Task Schemas ---

class TaskCreate(BaseModel):
    """Request to create a new task."""
    description: str = Field(..., min_length=1, max_length=5000)
    mode: str = Field(default="code")
    parent_id: str | None = None
    title: str = ""


class TaskResponse(BaseModel):
    """Task details response."""
    id: str
    parent_id: str | None
    root_id: str | None
    mode: str
    status: str
    title: str
    description: str
    working_directory: str
    created_at: datetime
    updated_at: datetime
    token_usage: TokenUsageResponse
    todo_list: list[TodoItemResponse] = []


class TaskListResponse(BaseModel):
    """List of tasks."""
    tasks: list[TaskResponse]


class TokenUsageResponse(BaseModel):
    """Token usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0


class TodoItemResponse(BaseModel):
    """A single todo item."""
    text: str
    done: bool


class TaskStatusUpdate(BaseModel):
    """Update task status."""
    status: str


class ModeSwitch(BaseModel):
    """Switch task mode."""
    mode: str


# --- Message Schemas ---

class MessageCreate(BaseModel):
    """Request to send a message."""
    content: str = Field(..., min_length=1, max_length=50000)


class MessageResponse(BaseModel):
    """Message details response."""
    id: str
    task_id: str
    role: str
    content: str
    created_at: datetime
    tool_calls: list[dict[str, Any]] = []


class MessageListResponse(BaseModel):
    """List of messages."""
    messages: list[MessageResponse]


# --- Mode Schemas ---

class ModeResponse(BaseModel):
    """Mode configuration response."""
    slug: str
    name: str
    when_to_use: str
    tool_groups: list[str]


class ModeListResponse(BaseModel):
    """List of available modes."""
    modes: list[ModeResponse]


# --- Approval Schemas ---

class ApprovalResponse(BaseModel):
    """Tool approval required."""
    approval_id: str
    tool_name: str
    params: dict[str, Any]


class ApprovalDecision(BaseModel):
    """User's decision on tool approval."""
    decision: str = Field(..., pattern="^(y|n|always)$")


# --- Input Schemas ---

class InputRequest(BaseModel):
    """Agent asking for user input."""
    input_id: str
    question: str
    suggestions: list[str] = []


class InputResponse(BaseModel):
    """User's response to input request."""
    answer: str


# --- Health ---

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# --- Error ---

class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str | None = None
