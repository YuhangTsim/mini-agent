"""OpenAI provider implementation."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import tiktoken
from openai import AsyncOpenAI

from .base import (
    BaseProvider,
    ModelInfo,
    StreamEvent,
    StreamEventType,
    ToolDefinition,
)


# Models that support vision
VISION_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision-preview"}


class OpenAIProvider(BaseProvider):
    """OpenAI API provider with streaming and function calling."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        try:
            self._encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    async def create_message(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat completion from OpenAI."""
        api_messages = [{"role": "system", "content": system_prompt}] + messages

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if tools:
            kwargs["tools"] = [self._tool_to_openai(t) for t in tools]

        stream = await self._client.chat.completions.create(**kwargs)

        # Track tool calls being built up across chunks
        active_tool_calls: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            if not chunk.choices and chunk.usage:
                # Final usage chunk
                yield StreamEvent(
                    type=StreamEventType.MESSAGE_END,
                    input_tokens=chunk.usage.prompt_tokens,
                    output_tokens=chunk.usage.completion_tokens,
                )
                continue

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Text content
            if delta.content:
                yield StreamEvent(type=StreamEventType.TEXT_DELTA, text=delta.content)

            # Tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in active_tool_calls:
                        active_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "args": "",
                        }
                        if tc.id:
                            active_tool_calls[idx]["id"] = tc.id

                    if tc.function:
                        if tc.function.name:
                            active_tool_calls[idx]["name"] = tc.function.name
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_START,
                                tool_call_id=active_tool_calls[idx]["id"],
                                tool_name=tc.function.name,
                            )
                        if tc.function.arguments:
                            active_tool_calls[idx]["args"] += tc.function.arguments
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                tool_call_id=active_tool_calls[idx]["id"],
                                tool_name=active_tool_calls[idx]["name"],
                                tool_args=tc.function.arguments,
                            )

            # Finish reason
            if chunk.choices[0].finish_reason:
                # Emit end events for all active tool calls
                for tc_data in active_tool_calls.values():
                    yield StreamEvent(
                        type=StreamEventType.TOOL_CALL_END,
                        tool_call_id=tc_data["id"],
                        tool_name=tc_data["name"],
                        tool_args=tc_data["args"],
                    )
                active_tool_calls.clear()

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="openai",
            model_id=self.model,
            max_context=128000,
            max_output=4096,
            supports_vision=self.model in VISION_MODELS,
            supports_tools=True,
        )

    @staticmethod
    def _tool_to_openai(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
