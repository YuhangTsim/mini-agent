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


# Provider model catalog - populated by registry
PROVIDER_MODELS: dict[str, list[ModelInfo]] = {
    "openai": [
        ModelInfo("openai", "gpt-4o", 128000, 4096, True, True),
        ModelInfo("openai", "gpt-4o-mini", 128000, 4096, True, True),
        ModelInfo("openai", "gpt-4-turbo", 128000, 4096, True, True),
        ModelInfo("openai", "gpt-3.5-turbo", 16385, 4096, False, True),
    ],
    "openrouter": [
        ModelInfo("openrouter", "anthropic/claude-sonnet-4-20250514", 200000, 8192, True, True),
        ModelInfo("openrouter", "anthropic/claude-opus-4", 200000, 8192, True, True),
        ModelInfo("openrouter", "openai/gpt-4o", 128000, 4096, True, True),
        ModelInfo("openrouter", "google/gemini-2.5-flash-preview", 1000000, 8192, True, True),
    ],
    "ollama": [
        ModelInfo("ollama", "llama3.2", 128000, 4096, False, True),
        ModelInfo("ollama", "qwen2.5", 128000, 4096, False, True),
        ModelInfo("ollama", "mistral", 128000, 4096, False, True),
    ],
}


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
