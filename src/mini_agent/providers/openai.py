"""OpenAI provider implementation."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
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

# Debug toggle: set DEBUG_LLM=1 to write request/response to a JSONL file
_DEBUG_LLM = os.environ.get("DEBUG_LLM", "").lower() in ("1", "true")
_DEBUG_DIR = Path(os.environ.get("DEBUG_LLM_DIR", "")) or Path.home() / ".mini-agent" / "debug"


def _debug_log(entry: dict[str, Any]) -> None:
    """Append a JSON line to the debug log file."""
    if not _DEBUG_LLM:
        return
    _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = _DEBUG_DIR / "llm_calls.jsonl"
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


class OpenAIProvider(BaseProvider):
    """OpenAI API provider with streaming and function calling."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        self.model = model
        self._base_url = base_url
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

        # Debug: log the request
        if _DEBUG_LLM:
            _debug_log({
                "direction": "request",
                "model": self.model,
                "base_url": self._base_url,
                "system_prompt_len": len(system_prompt),
                "system_prompt": system_prompt[:500] + ("..." if len(system_prompt) > 500 else ""),
                "messages": api_messages,
                "tools": [t.name for t in tools] if tools else None,
                "max_tokens": max_tokens,
                "temperature": temperature,
            })

        start_time = time.monotonic()

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            if _DEBUG_LLM:
                _debug_log({"direction": "error", "error": str(e)})
            raise

        # Track tool calls being built up across chunks
        active_tool_calls: dict[int, dict[str, str]] = {}

        # Track accumulated output for token estimation fallback
        accumulated_text = ""
        accumulated_tool_args = ""
        got_usage = False

        async for chunk in stream:
            if not chunk.choices and chunk.usage:
                # Final usage chunk
                got_usage = True
                if _DEBUG_LLM:
                    _debug_log({
                        "direction": "response_end",
                        "duration_ms": int((time.monotonic() - start_time) * 1000),
                        "input_tokens": chunk.usage.prompt_tokens,
                        "output_tokens": chunk.usage.completion_tokens,
                        "text_len": len(accumulated_text),
                        "text_preview": accumulated_text[:500] + ("..." if len(accumulated_text) > 500 else ""),
                        "tool_calls": list(active_tool_calls.values()) if active_tool_calls else None,
                    })
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
                accumulated_text += delta.content
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
                            accumulated_tool_args += tc.function.arguments
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

        # Fallback: if the API didn't send a usage chunk, estimate tokens
        if not got_usage:
            output_text = accumulated_text + accumulated_tool_args
            estimated_output = self.count_tokens(output_text) if output_text else 0
            # Rough input estimate: count tokens in the serialized messages
            input_text = system_prompt + json.dumps(api_messages, default=str)
            estimated_input = self.count_tokens(input_text)
            if _DEBUG_LLM:
                _debug_log({
                    "direction": "response_end",
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                    "input_tokens": estimated_input,
                    "output_tokens": estimated_output,
                    "estimated": True,
                    "text_len": len(accumulated_text),
                    "text_preview": accumulated_text[:500] + ("..." if len(accumulated_text) > 500 else ""),
                    "tool_calls": [
                        {"name": tc["name"], "args_len": len(tc["args"])}
                        for tc in active_tool_calls.values()
                    ] if active_tool_calls else None,
                })
            yield StreamEvent(
                type=StreamEventType.MESSAGE_END,
                input_tokens=estimated_input,
                output_tokens=estimated_output,
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
                "strict": True,
                "parameters": tool.parameters,
            },
        }
