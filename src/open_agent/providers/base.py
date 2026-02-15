"""Abstract provider interface for LLM backends."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator


class StreamEventType(str, enum.Enum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_END = "tool_call_end"
    MESSAGE_END = "message_end"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: StreamEventType
    text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    tool_args: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str = ""


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


@dataclass
class ModelInfo:
    provider: str
    model_id: str
    max_context: int = 128000
    max_output: int = 4096
    supports_vision: bool = False
    supports_tools: bool = True


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def create_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncIterator[StreamEvent]:
        """Send messages and stream back response events."""
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get information about the current model."""
        ...
