"""Agent loop: message -> LLM -> tool -> response cycle."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

import platform

from ..persistence.models import (
    Message,
    MessageRole,
    Task,
    TaskStatus,
    TokenUsage,
    TodoItem,
    ToolCall,
)
from ..persistence.store import Store
from agent_kernel.providers.base import BaseProvider, StreamEventType, ToolDefinition
from ..tools.base import ApprovalPolicy, ToolContext, ToolRegistry, ToolResult
from ..config.settings import Settings
from .mode import ModeConfig, get_mode


@dataclass
class AgentCallbacks:
    """Callbacks for agent events that the UI/CLI handles."""

    on_text_delta: Callable[[str], Awaitable[None]] | None = None
    on_tool_call_start: Callable[[str, str, str], Awaitable[None]] | None = None  # id, name, args
    on_tool_call_end: Callable[[str, str, ToolResult], Awaitable[None]] | None = None
    on_tool_approval_request: Callable[[str, str, dict], Awaitable[str]] | None = (
        None  # name, id, params -> "y"/"n"/"always"
    )
    request_user_input: Callable[[str, list[str] | None], Awaitable[str]] | None = None
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

    def _build_system_prompt(self, mode: ModeConfig, task: Task) -> str:
        """Build a system prompt from mode config for child tasks and mode switches.

        Uses the same structure as PromptBuilder but without needing the full
        settings/skills context.  Good enough for recursive child tasks.
        """
        working_dir = task.working_directory or self.settings.working_directory

        parts = [
            mode.role_definition,
            "",
            "====",
            "",
            "TOOL USE",
            "",
            (
                "You have access to a set of tools that are executed upon the user's approval. "
                "Use the provider-native tool-calling mechanism. You must call at least one tool "
                "per assistant response when working on a task."
            ),
            "",
            "====",
            "",
            "RULES",
            "",
            f"- The project base directory is: {working_dir}",
            "- All file paths must be relative to this directory unless absolute paths are specified.",
            "- Always read a file before editing it.",
            "- When you've completed your task, you must use the attempt_completion tool to present the result.",
            "- NEVER end attempt_completion result with a question or request for further conversation.",
            "- Your goal is to accomplish the user's task, NOT engage in back and forth conversation.",
        ]

        if mode.custom_instructions:
            parts.extend(["", "## Mode-Specific Instructions", mode.custom_instructions])

        parts.extend(
            [
                "",
                "====",
                "",
                "SYSTEM INFORMATION",
                "",
                f"Operating System: {platform.system()}",
                f"Current Workspace Directory: {working_dir}",
                f"Current Mode: {mode.name} ({mode.slug})",
                "",
                "====",
                "",
                "OBJECTIVE",
                "",
                "You accomplish the given task iteratively, breaking it down into clear steps.",
                "Once you've completed the task, use the attempt_completion tool to present the result.",
            ]
        )

        return "\n".join(parts)

    async def _run_child_task(self, parent_task: Task, mode_slug: str, description: str) -> str:
        """Create and run a child task, returning its result."""
        child_mode = get_mode(mode_slug)
        child_task = Task(
            parent_id=parent_task.id,
            root_id=parent_task.root_id or parent_task.id,
            mode=mode_slug,
            status=TaskStatus.ACTIVE,
            title=description[:100],
            description=description,
            working_directory=parent_task.working_directory or self.settings.working_directory,
        )
        await self.store.add_task(child_task)
        parent_task.children.append(child_task.id)

        child_system_prompt = self._build_system_prompt(child_mode, child_task)
        child_result = await self.run(
            task=child_task,
            user_message=description,
            conversation=[],
            system_prompt=child_system_prompt,
        )
        return child_task.result or child_result or "(child task produced no output)"

    def _build_todo_directive(self, task: Task) -> str | None:
        """If the task has pending todo items, return a directive for the LLM."""
        pending = [item for item in task.todo_list if not item.done]
        if not pending:
            return None

        done = [item for item in task.todo_list if item.done]
        lines = ["## Plan Execution Status", ""]
        if done:
            for item in done:
                lines.append(f"- [x] {item.text}")
        for item in pending:
            lines.append(f"- [ ] {item.text}")

        lines.extend(
            [
                "",
                f"Next pending item: **{pending[0].text}**",
                "",
                "Instructions:",
                "- If this item is straightforward, execute it directly using your tools.",
                "- If this item is complex or isolated, delegate it using the new_task tool.",
                "- After completing an item, call update_todo_list to mark it done.",
                "- Do NOT use attempt_completion until all items are done.",
            ]
        )
        return "\n".join(lines)

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
        todo_injection_count = 0
        max_todo_injections = 15  # Subset of max_iterations
        final_text = ""
        loop_completed_normally = True

        for iteration in range(max_iterations):
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
                    pending_tool_calls.append(
                        {
                            "id": event.tool_call_id,
                            "name": event.tool_name,
                            "args": event.tool_args,
                        }
                    )

                elif event.type == StreamEventType.MESSAGE_END:
                    usage.input_tokens = event.input_tokens
                    usage.output_tokens = event.output_tokens

            # Update token tracking
            task.token_usage.add(usage)

            # If no tool calls, we're done
            if not pending_tool_calls:
                if self.callbacks.on_message_end:
                    await self.callbacks.on_message_end(usage)
                if text_response:
                    final_text = text_response
                    # Store assistant message
                    assistant_msg = Message.from_text(task.id, MessageRole.ASSISTANT, text_response)
                    assistant_msg.token_count = self.provider.count_tokens(text_response)
                    await self.store.add_message(assistant_msg)
                    conversation.append({"role": "assistant", "content": text_response})
                loop_completed_normally = False
                break

            # Has tool calls — defer on_message_end until after tool execution
            # so token counts don't appear between tool name and tool result.

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
            assistant_content = (
                text_response
                or f"[Tool calls: {', '.join(tc['name'] for tc in pending_tool_calls)}]"
            )
            assistant_msg = Message.from_text(task.id, MessageRole.ASSISTANT, assistant_content)
            await self.store.add_message(assistant_msg)

            # Execute tool calls, collecting results with conversation indices
            tool_results: list[tuple[dict[str, str], ToolResult, int]] = []
            for tc in pending_tool_calls:
                result = await self._execute_tool_call(
                    task=task,
                    mode=mode,
                    tool_call_id=tc["id"],
                    tool_name=tc["name"],
                    tool_args_str=tc["args"],
                )

                # Add tool result to conversation (OpenAI format)
                tool_content = result.output if not result.is_error else f"Error: {result.error}"
                conv_index = len(conversation)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    }
                )
                tool_results.append((tc, result, conv_index))

            # Now emit on_message_end (after tool results are displayed)
            if self.callbacks.on_message_end:
                await self.callbacks.on_message_end(usage)

            # --- Process agent signals from tool results ---
            signal_break = False
            signal_continue = False

            for tc, result, conv_idx in tool_results:
                if result.is_error:
                    continue
                output = result.output

                # attempt_completion: mark task done and break
                if output.startswith("__attempt_completion__:"):
                    result_text = output[len("__attempt_completion__:") :]
                    task.status = TaskStatus.COMPLETED
                    task.result = result_text
                    final_text = result_text
                    # Replace raw signal in conversation with friendly message
                    conversation[conv_idx]["content"] = f"Task completed: {result_text}"
                    signal_break = True
                    break

                # switch_mode: update mode, rebuild tools/prompt, continue
                if output.startswith("__switch_mode__:"):
                    payload = output[len("__switch_mode__:") :]
                    parts = payload.split(":", 1)
                    new_mode_slug = parts[0]
                    reason = parts[1] if len(parts) > 1 else ""
                    try:
                        mode = get_mode(new_mode_slug)
                    except KeyError:
                        conversation[conv_idx]["content"] = f"Error: unknown mode '{new_mode_slug}'"
                        continue
                    task.mode = new_mode_slug
                    available_tools = self.registry.get_tools_for_mode(mode.tool_groups)
                    tool_definitions = [
                        ToolDefinition(
                            name=t.name,
                            description=t.description,
                            parameters=t.parameters,
                        )
                        for t in available_tools
                    ]
                    system_prompt = self._build_system_prompt(mode, task)
                    friendly = f"Switched to {mode.name} mode."
                    if reason:
                        friendly += f" Reason: {reason}"
                    conversation[conv_idx]["content"] = friendly
                    signal_continue = True
                    continue

                # new_task: run child task, feed result back
                if output.startswith("__new_task__:"):
                    payload = output[len("__new_task__:") :]
                    parts = payload.split(":", 1)
                    child_mode = parts[0]
                    child_desc = parts[1] if len(parts) > 1 else ""
                    child_result = await self._run_child_task(task, child_mode, child_desc)
                    conversation[conv_idx]["content"] = f"Sub-task result:\n{child_result}"
                    signal_continue = True
                    continue

            if signal_break:
                loop_completed_normally = False
                break
            if signal_continue:
                continue

            # --- Active todo execution: if pending items exist, inject directive ---
            directive = self._build_todo_directive(task)
            if directive:
                todo_injection_count += 1
                if todo_injection_count <= max_todo_injections:
                    conversation.append({"role": "user", "content": directive})

            # Continue loop — LLM will process tool results

        # Warn if max_iterations exhausted without a clean exit
        if loop_completed_normally:
            warning = (
                f"\n⚠ Reached maximum iterations ({max_iterations}) without completing. "
                "The task may be incomplete. Consider breaking it into smaller steps."
            )
            if self.callbacks.on_text_delta:
                await self.callbacks.on_text_delta(warning)
            if not final_text:
                final_text = warning

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
            await self._store_tool_call(
                task.id, tool_name, tool_args_str, result, 0, status="denied"
            )
            return result

        if tool.skip_approval:
            pass  # Skip approval flow entirely (e.g., ask_followup_question)
        elif policy in (ApprovalPolicy.ALWAYS_ASK, ApprovalPolicy.ASK_ONCE):
            if self.callbacks.on_tool_approval_request:
                response = await self.callbacks.on_tool_approval_request(
                    tool_name, tool_call_id, params
                )
                if response == "always":
                    self.registry.set_session_approval(tool_name, True)
                elif response != "y":
                    result = ToolResult.failure(f"Tool '{tool_name}' was denied by user.")
                    await self._store_tool_call(
                        task.id, tool_name, tool_args_str, result, 0, status="denied"
                    )
                    if self.callbacks.on_tool_call_end:
                        await self.callbacks.on_tool_call_end(tool_call_id, tool_name, result)
                    return result

        # Execute
        context = ToolContext(
            session_id=task.id,
            agent_role=task.mode,
            working_directory=task.working_directory or self.settings.working_directory,
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
                    task.todo_list = [
                        TodoItem(text=i["text"], done=i.get("done", False)) for i in items
                    ]
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
