"""Agent loop: message -> LLM -> tool -> response cycle."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Awaitable

from ..persistence.models import (
    Message, MessageRole, Task, TokenUsage, TodoItem, ToolCall, new_id,
)
from ..persistence.store import Store
from ..providers.base import BaseProvider, StreamEvent, StreamEventType, ToolDefinition
from ..tools.base import ApprovalPolicy, BaseTool, ToolContext, ToolRegistry, ToolResult
from ..config.settings import Settings
from .mode import ModeConfig, get_mode


@dataclass
class AgentCallbacks:
    """Callbacks for agent events that the UI/CLI handles."""

    on_text_delta: Callable[[str], Awaitable[None]] | None = None
    on_tool_call_start: Callable[[str, str, str], Awaitable[None]] | None = None  # id, name, args
    on_tool_call_end: Callable[[str, str, ToolResult], Awaitable[None]] | None = None
    on_tool_approval_request: Callable[[str, str, dict], Awaitable[str]] | None = None  # name, id, params -> "y"/"n"/"always"
    request_user_input: Callable[[str], Awaitable[str]] | None = None
    on_message_end: Callable[[TokenUsage], Awaitable[None]] | None = None


class Agent:
    """Core agent that runs the LLM -> tool -> response loop."""

    def __init__(
        self,
        provider: BaseProvider,
        registry: ToolRegistry,
        store: Store,
        settings: Settings,
        callbacks: AgentCallbacks | None = None,
    ):
        self.provider = provider
        self.registry = registry
        self.store = store
        self.settings = settings
        self.callbacks = callbacks or AgentCallbacks()

    async def run(
        self,
        task: Task,
        user_message: str,
        conversation: list[dict[str, Any]],
        system_prompt: str,
    ) -> str:
        """Run a single agent turn: send user message, handle tool calls, return final text.

        May run multiple LLM calls if tool calls are needed.
        Returns the final assistant text response.
        """
        mode = get_mode(task.mode)
        available_tools = self.registry.get_tools_for_mode(mode.tool_groups)
        tool_definitions = [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in available_tools
        ]

        # Add user message to conversation
        conversation.append({"role": "user", "content": user_message})

        # Store user message
        user_msg = Message.from_text(task.id, MessageRole.USER, user_message)
        await self.store.add_message(user_msg)

        max_iterations = 25  # Safety limit for tool call loops
        final_text = ""

        for _ in range(max_iterations):
            # Call LLM
            text_response = ""
            pending_tool_calls: list[dict[str, str]] = []
            usage = TokenUsage()

            stream = self.provider.create_message(
                system_prompt=system_prompt,
                messages=conversation,
                tools=tool_definitions if available_tools else None,
                max_tokens=self.settings.provider.max_tokens,
                temperature=self.settings.provider.temperature,
            )

            async for event in stream:
                if event.type == StreamEventType.TEXT_DELTA:
                    text_response += event.text
                    if self.callbacks.on_text_delta:
                        await self.callbacks.on_text_delta(event.text)

                elif event.type == StreamEventType.TOOL_CALL_START:
                    if self.callbacks.on_tool_call_start:
                        await self.callbacks.on_tool_call_start(
                            event.tool_call_id, event.tool_name, ""
                        )

                elif event.type == StreamEventType.TOOL_CALL_END:
                    pending_tool_calls.append({
                        "id": event.tool_call_id,
                        "name": event.tool_name,
                        "args": event.tool_args,
                    })

                elif event.type == StreamEventType.MESSAGE_END:
                    usage.input_tokens = event.input_tokens
                    usage.output_tokens = event.output_tokens

            # Update token tracking
            task.token_usage.add(usage)
            if self.callbacks.on_message_end:
                await self.callbacks.on_message_end(usage)

            # If no tool calls, we're done
            if not pending_tool_calls:
                if text_response:
                    final_text = text_response
                    # Store assistant message
                    assistant_msg = Message.from_text(
                        task.id, MessageRole.ASSISTANT, text_response
                    )
                    assistant_msg.token_count = self.provider.count_tokens(text_response)
                    await self.store.add_message(assistant_msg)
                    conversation.append({"role": "assistant", "content": text_response})
                break

            # Build the assistant message with tool calls for conversation history
            assistant_message: dict[str, Any] = {"role": "assistant"}
            if text_response:
                assistant_message["content"] = text_response
            else:
                assistant_message["content"] = None

            # OpenAI format: tool_calls in assistant message
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["args"],
                    },
                }
                for tc in pending_tool_calls
            ]
            conversation.append(assistant_message)

            # Store assistant message
            assistant_content = text_response or f"[Tool calls: {', '.join(tc['name'] for tc in pending_tool_calls)}]"
            assistant_msg = Message.from_text(
                task.id, MessageRole.ASSISTANT, assistant_content
            )
            await self.store.add_message(assistant_msg)

            # Execute tool calls
            for tc in pending_tool_calls:
                result = await self._execute_tool_call(
                    task=task,
                    mode=mode,
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    tool_args_str=tc["args"],
                )

                # Add tool result to conversation (OpenAI format)
                conversation.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result.output if not result.is_error else f"Error: {result.error}",
                })

            # Continue loop — LLM will process tool results

        await self.store.update_task(task)
        return final_text

    async def _execute_tool_call(
        self,
        task: Task,
        mode: ModeConfig,
        tool_call_id: str,
        tool_name: str,
        tool_args_str: str,
    ) -> ToolResult:
        """Execute a single tool call with approval flow."""
        tool = self.registry.get(tool_name)
        if tool is None:
            result = ToolResult.failure(f"Unknown tool: {tool_name}")
            await self._store_tool_call(task.id, tool_name, tool_args_str, result, 0)
            return result

        # Parse arguments
        try:
            params = json.loads(tool_args_str) if tool_args_str else {}
        except json.JSONDecodeError:
            result = ToolResult.failure(f"Invalid JSON arguments: {tool_args_str}")
            await self._store_tool_call(task.id, tool_name, tool_args_str, result, 0)
            return result

        # Check file restrictions for mode
        if mode.file_restrictions and tool_name in ("write_file", "edit_file"):
            import re
            restriction = mode.file_restrictions.get("edit")
            if restriction and "path" in params:
                if not re.search(restriction, params["path"]):
                    result = ToolResult.failure(
                        f"Mode '{mode.slug}' restricts edits to files matching: {restriction}"
                    )
                    await self._store_tool_call(task.id, tool_name, tool_args_str, result, 0)
                    return result

        # Approval flow
        policy_str = self.settings.approval.get_policy(tool_name)
        policy = self.registry.check_approval(tool_name, policy_str)

        if policy == ApprovalPolicy.DENY:
            result = ToolResult.failure(f"Tool '{tool_name}' is denied by policy.")
            await self._store_tool_call(task.id, tool_name, tool_args_str, result, 0, status="denied")
            return result

        if policy in (ApprovalPolicy.ALWAYS_ASK, ApprovalPolicy.ASK_ONCE):
            if self.callbacks.on_tool_approval_request:
                response = await self.callbacks.on_tool_approval_request(
                    tool_name, tool_call_id, params
                )
                if response == "always":
                    self.registry.set_session_approval(tool_name, True)
                elif response != "y":
                    result = ToolResult.failure(f"Tool '{tool_name}' was denied by user.")
                    await self._store_tool_call(task.id, tool_name, tool_args_str, result, 0, status="denied")
                    if self.callbacks.on_tool_call_end:
                        await self.callbacks.on_tool_call_end(tool_call_id, tool_name, result)
                    return result

        # Execute
        context = ToolContext(
            task_id=task.id,
            working_directory=task.working_directory or self.settings.working_directory,
            mode=task.mode,
            request_user_input=self.callbacks.request_user_input,
        )

        start = time.monotonic()
        try:
            result = await tool.execute(params, context)
        except Exception as e:
            result = ToolResult.failure(f"Tool execution error: {e}")
        duration_ms = int((time.monotonic() - start) * 1000)

        # Handle todo list updates
        if tool_name == "update_todo_list" and not result.is_error:
            marker = "__todo_data__:"
            if marker in result.output:
                todo_json = result.output.split(marker, 1)[1]
                try:
                    items = json.loads(todo_json)
                    task.todo_list = [TodoItem(text=i["text"], done=i.get("done", False)) for i in items]
                except (json.JSONDecodeError, KeyError):
                    pass

        await self._store_tool_call(task.id, tool_name, tool_args_str, result, duration_ms)

        if self.callbacks.on_tool_call_end:
            await self.callbacks.on_tool_call_end(tool_call_id, tool_name, result)

        return result

    async def _store_tool_call(
        self,
        task_id: str,
        tool_name: str,
        params_str: str,
        result: ToolResult,
        duration_ms: int,
        status: str | None = None,
    ) -> None:
        tc = ToolCall(
            task_id=task_id,
            tool_name=tool_name,
            parameters=params_str,
            result=result.output if not result.is_error else result.error,
            status=status or ("error" if result.is_error else "success"),
            duration_ms=duration_ms,
        )
        await self.store.add_tool_call(tc)
