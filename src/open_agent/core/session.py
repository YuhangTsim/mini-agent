"""SessionProcessor: LLM→tool loop for a single agent."""

from __future__ import annotations

import inspect
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, cast

from open_agent.agents.base import BaseAgent
from open_agent.bus import Event, EventBus
from open_agent.config.settings import CompactionSettings
from open_agent.core.context.manager import CompactionManager
from open_agent.persistence.models import (
    AgentRun,
    AgentRunStatus,
    Message,
    MessagePart,
    MessageRole,
    SessionMessage,
    TodoItem,
    TokenUsage,
    ToolCall,
    utcnow,
)
from open_agent.persistence.store import Store
from open_agent.providers.base import BaseProvider, StreamEvent, StreamEventType, ToolDefinition
from agent_kernel.tool_calling import (
    DEFAULT_INVALID_TOOL_TURN_LIMIT,
    build_non_convergence_message,
)
from agent_kernel.tools.base import ApprovalPolicy
from open_agent.tools.base import ToolContext, ToolRegistry, ToolResult
from open_agent.tools.permissions import PermissionChecker
from open_agent.hooks import HookContext, HookPoint, HookRegistry

logger = logging.getLogger(__name__)


@dataclass
class SessionCallbacks:
    """Callbacks for UI events during session processing."""

    on_thinking_delta: Callable[[str], Awaitable[None]] | None = None
    on_text_delta: Callable[[str], Awaitable[None]] | None = None
    on_tool_call_start: Callable[[str, str, str], Awaitable[None]] | None = None
    on_tool_call_end: Callable[[str, str, ToolResult], Awaitable[None]] | None = None
    on_tool_approval_request: Callable[[str, str, dict], Awaitable[str]] | None = None
    request_user_input: Callable[[str, list[str] | None], Awaitable[str]] | None = None
    on_message_end: Callable[[TokenUsage], Awaitable[None]] | None = None


class SessionProcessor:
    """Runs the LLM→tool loop for a single agent.

    When the agent calls delegate_task, the processor delegates to a
    DelegationManager (injected as a callback). When the agent calls
    report_result, the loop ends and returns the result.
    """

    def __init__(
        self,
        agent: BaseAgent,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        permission_checker: PermissionChecker,
        hook_registry: HookRegistry,
        bus: EventBus,
        store: Store,
        working_directory: str,
        callbacks: SessionCallbacks | None = None,
        delegation_handler: Callable[..., Awaitable[str]] | None = None,
        background_handler: Callable[..., Awaitable[str]] | None = None,
        background_status_handler: Callable[..., Awaitable[str]] | None = None,
        compaction_settings: CompactionSettings | None = None,
        persist_session_transcript: bool = False,
    ) -> None:
        self.agent = agent
        self.provider = provider
        self.tool_registry = tool_registry
        self.permission_checker = permission_checker
        self.hook_registry = hook_registry
        self.bus = bus
        self.store = store
        self.working_directory = working_directory
        self.callbacks = callbacks or SessionCallbacks()
        self._delegation_handler = delegation_handler
        self._background_handler = background_handler
        self._background_status_handler = background_status_handler
        self._persist_session_transcript = persist_session_transcript
        
        # Initialize compaction manager if enabled
        self._compaction_manager: CompactionManager | None = None
        if compaction_settings and compaction_settings.enabled and compaction_settings.auto:
            self._compaction_manager = CompactionManager(
                store=store,
                provider=provider,
                bus=bus,
                settings=compaction_settings,
            )

    async def process(
        self,
        agent_run: AgentRun,
        user_message: str,
        conversation: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Run the LLM→tool loop for this agent.

        Returns the final result text.
        """
        if conversation is None:
            conversation = []

        if system_prompt is None:
            system_prompt = self.agent.get_system_prompt(
                {"working_directory": self.working_directory}
            )

        # Get tools available to this agent
        allowed, denied = self.agent.get_tool_filter()
        available_tools = self.tool_registry.get_tools_for_agent(
            allowed=allowed or None, denied=denied or None
        )
        tool_definitions = [
            ToolDefinition(name=t.name, description=t.description, parameters=t.parameters)
            for t in available_tools
        ]

        # Add user message
        conversation.append({"role": "user", "content": user_message})
        user_msg = Message.from_text(agent_run.id, MessageRole.USER, user_message)
        await self.store.add_message(user_msg)
        await self._store_session_message(
            agent_run=agent_run,
            role=MessageRole.USER,
            content=user_message,
        )

        await self.bus.publish(
            Event.AGENT_START,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"run_id": agent_run.id, "description": agent_run.description},
        )

        max_iterations = self.agent.config.max_iterations
        invalid_tool_turn_limit = DEFAULT_INVALID_TOOL_TURN_LIMIT
        consecutive_invalid_tool_turns = 0
        final_text = ""

        for iteration in range(max_iterations):
            # Before LLM call hook
            hook_ctx = HookContext(
                session_id=agent_run.session_id,
                agent_role=self.agent.role,
                data={"iteration": iteration},
            )
            hook_result = await self.hook_registry.run(HookPoint.BEFORE_LLM_CALL, hook_ctx)
            if hook_result.cancelled:
                final_text = f"LLM call cancelled by hook: {hook_result.reason}"
                break

            # Check and compact context if needed
            if self._compaction_manager is not None:
                current_tokens = self._estimate_tokens(conversation)
                compaction_result = await self._compaction_manager.check_and_compact(
                    session_id=agent_run.session_id,
                    agent_run=agent_run,
                    current_tokens=current_tokens,
                )
                if compaction_result and compaction_result.summary:
                    # Add compaction summary to conversation
                    conversation.append({
                        "role": "system",
                        "content": f"[Previous conversation summary]: {compaction_result.summary}",
                    })
                    logger.debug(
                        f"Added compaction summary to conversation, "
                        f"saved ~{compaction_result.tokens_before - compaction_result.tokens_after} tokens"
                    )

            # Call LLM
            text_response = ""
            thinking_response = ""
            pending_tool_calls: list[dict[str, str]] = []
            usage = TokenUsage()

            stream_candidate: AsyncIterator[StreamEvent] | Awaitable[AsyncIterator[StreamEvent]] = (
                self.provider.create_message(
                    system_prompt=system_prompt,
                    messages=conversation,
                    tools=tool_definitions if available_tools else None,
                    max_tokens=self.agent.config.max_tokens,
                    temperature=self.agent.config.temperature,
                    thinking_budget_tokens=self.agent.config.thinking_budget_tokens,
                )
            )
            if inspect.iscoroutine(stream_candidate):
                stream = await stream_candidate
            else:
                stream = cast(AsyncIterator[StreamEvent], stream_candidate)

            async for event in stream:
                if event.type == StreamEventType.THINKING_DELTA:
                    thinking_response += event.text
                    if self.callbacks.on_thinking_delta:
                        await self.callbacks.on_thinking_delta(event.text)
                    await self.bus.publish(
                        Event.THINKING_STREAM,
                        session_id=agent_run.session_id,
                        agent_role=self.agent.role,
                        data={"token": event.text, "run_id": agent_run.id},
                    )

                elif event.type == StreamEventType.TEXT_DELTA:
                    text_response += event.text
                    if self.callbacks.on_text_delta:
                        await self.callbacks.on_text_delta(event.text)
                    await self.bus.publish(
                        Event.TOKEN_STREAM,
                        session_id=agent_run.session_id,
                        agent_role=self.agent.role,
                        data={"token": event.text, "run_id": agent_run.id},
                    )

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

            agent_run.token_usage.add(usage)

            # No tool calls → done
            if not pending_tool_calls:
                if self.callbacks.on_message_end:
                    await self.callbacks.on_message_end(usage)
                if text_response:
                    final_text = text_response
                    assistant_msg = Message.from_text(
                        agent_run.id, MessageRole.ASSISTANT, text_response
                    )
                    await self.store.add_message(assistant_msg)
                    await self._store_thinking_if_present(assistant_msg, thinking_response)
                    await self._store_session_message(
                        agent_run=agent_run,
                        role=MessageRole.ASSISTANT,
                        content=text_response,
                    )
                    conversation.append({"role": "assistant", "content": text_response})
                break

            # Build assistant message with tool calls
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": text_response or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]},
                    }
                    for tc in pending_tool_calls
                ],
            }
            conversation.append(assistant_message)

            is_report_result_only = (
                len(pending_tool_calls) == 1 and pending_tool_calls[0]["name"] == "report_result"
            )
            if not is_report_result_only:
                await self._store_session_message(
                    agent_run=agent_run,
                    role=MessageRole.ASSISTANT,
                    content=text_response,
                    tool_calls=assistant_message["tool_calls"],
                )

            assistant_content = (
                text_response
                or f"[Tool calls: {', '.join(tc['name'] for tc in pending_tool_calls)}]"
            )
            assistant_msg = Message.from_text(
                agent_run.id, MessageRole.ASSISTANT, assistant_content
            )
            await self.store.add_message(assistant_msg)
            await self._store_thinking_if_present(assistant_msg, thinking_response)

            # Execute tool calls
            should_break = False
            turn_results: list[ToolResult] = []
            for tc in pending_tool_calls:
                result = await self._execute_pending_tool_call(agent_run, tc)
                turn_results.append(result)

                if tc["name"] == "report_result" and not result.is_error:
                    result_text = result.output.removeprefix("Result reported: ")
                    final_text = result_text
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": result.output,
                        }
                    )
                    await self._store_session_message(
                        agent_run=agent_run,
                        role=MessageRole.ASSISTANT,
                        content=result_text,
                    )
                    should_break = True
                    break

                tool_content = result.output if not result.is_error else f"Error: {result.error}"
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_content,
                    }
                )
                await self._store_session_message(
                    agent_run=agent_run,
                    role=MessageRole.TOOL,
                    content=tool_content,
                    tool_call_id=tc["id"],
                )

            if self.callbacks.on_message_end:
                await self.callbacks.on_message_end(usage)

            if turn_results and all(result.is_error for result in turn_results):
                consecutive_invalid_tool_turns += 1
            else:
                consecutive_invalid_tool_turns = 0

            if consecutive_invalid_tool_turns >= invalid_tool_turn_limit:
                final_text = build_non_convergence_message(
                    invalid_tool_turns=consecutive_invalid_tool_turns,
                    invalid_tool_turn_limit=invalid_tool_turn_limit,
                )
                agent_run.status = AgentRunStatus.FAILED
                agent_run.result = final_text
                agent_run.completed_at = utcnow()
                assistant_msg = Message.from_text(agent_run.id, MessageRole.ASSISTANT, final_text)
                await self.store.add_message(assistant_msg)
                await self._store_session_message(
                    agent_run=agent_run,
                    role=MessageRole.ASSISTANT,
                    content=final_text,
                )
                if self.callbacks.on_text_delta:
                    await self.callbacks.on_text_delta(final_text)
                break

            if should_break:
                break
        else:
            # Max iterations reached
            final_text = (
                f"Reached maximum iterations ({max_iterations}) without completing. "
                "The task may be incomplete."
            )

        # Update run status
        if agent_run.status == AgentRunStatus.RUNNING:
            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = utcnow()
            if not agent_run.result:
                agent_run.result = final_text
        await self.store.update_agent_run(agent_run)

        await self.bus.publish(
            Event.AGENT_END,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"run_id": agent_run.id, "result": final_text},
        )

        return final_text

    async def _execute_pending_tool_call(
        self,
        agent_run: AgentRun,
        tc: dict[str, str],
    ) -> ToolResult:
        """Execute a tool call after parsing model-provided JSON arguments."""
        tool_name = tc["name"]
        tool_args_str = tc["args"]

        try:
            params = json.loads(tool_args_str) if tool_args_str else {}
        except json.JSONDecodeError:
            result = ToolResult.failure(f"Invalid JSON arguments: {tool_args_str}")
            await self._store_tool_call(agent_run.id, tool_name, tool_args_str, result, 0)
            return result

        if tool_name == "delegate_task" and self._delegation_handler:
            return await self._handle_delegation(agent_run, tc, params)
        if tool_name == "delegate_background" and self._background_handler:
            return await self._handle_background(agent_run, tc, params)
        if tool_name == "check_background_task" and self._background_status_handler:
            task_id = params.get("task_id", "")
            status_text = await self._background_status_handler(task_id)
            return ToolResult.success(status_text)
        if tool_name == "report_result":
            result_text = params.get("result", "")
            agent_run.result = result_text
            agent_run.status = AgentRunStatus.COMPLETED
            agent_run.completed_at = utcnow()
            return ToolResult.success(f"Result reported: {result_text}")
        if tool_name == "todo_write":
            return await self._handle_todo_write(agent_run, tc, params)
        if tool_name == "todo_read":
            return await self._handle_todo_read(agent_run, tc, params)
        return await self._execute_tool(agent_run, tc, params)

    async def _store_thinking_if_present(
        self, assistant_msg: Message, thinking_response: str
    ) -> None:
        """Persist thinking content as a message part if present."""
        if thinking_response:
            await self.store.add_message_part(
                MessagePart(
                    message_id=assistant_msg.id,
                    part_type="thinking",
                    content=thinking_response,
                )
            )

    async def _store_session_message(
        self,
        agent_run: AgentRun,
        role: MessageRole,
        content: str | None,
        tool_call_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        kind: str = "message",
    ) -> None:
        """Persist a replayable transcript event for top-level user-visible history."""
        if not self._persist_session_transcript:
            return

        sequence = await self.store.get_next_session_sequence(agent_run.session_id)
        session_message = SessionMessage(
            session_id=agent_run.session_id,
            sequence=sequence,
            source_run_id=agent_run.id,
            agent_role=self.agent.role,
            role=role,
            kind=kind,
            content=content or "",
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
        )
        await self.store.add_session_message(session_message)

    async def _handle_delegation(
        self, agent_run: AgentRun, tc: dict[str, str], params: dict
    ) -> ToolResult:
        """Handle a delegate_task tool call."""
        target_role = params.get("agent_role", "")
        description = params.get("description", "")

        if not self.agent.can_delegate(target_role):
            return ToolResult.failure(
                f"Agent '{self.agent.role}' cannot delegate to '{target_role}'. "
                f"Allowed: {self.agent.config.can_delegate_to}"
            )

        await self.bus.publish(
            Event.DELEGATION_START,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"target_role": target_role, "description": description},
        )

        handler = self._delegation_handler
        assert handler is not None
        try:
            result_text = await handler(
                from_run=agent_run,
                target_role=target_role,
                description=description,
            )
        except Exception as e:
            result_text = f"Delegation failed: {e}"

        await self.bus.publish(
            Event.DELEGATION_END,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"target_role": target_role, "result": result_text[:200]},
        )

        return ToolResult.success(f"Delegation result from {target_role}:\n{result_text}")

    async def _handle_background(
        self, agent_run: AgentRun, tc: dict[str, str], params: dict
    ) -> ToolResult:
        """Handle a delegate_background tool call."""
        target_role = params.get("agent_role", "")
        description = params.get("description", "")

        if not self.agent.can_delegate(target_role):
            return ToolResult.failure(
                f"Agent '{self.agent.role}' cannot delegate to '{target_role}'."
            )

        handler = self._background_handler
        assert handler is not None
        try:
            task_id = await handler(
                from_run=agent_run,
                target_role=target_role,
                description=description,
            )
        except Exception as e:
            return ToolResult.failure(f"Background delegation failed: {e}")

        return ToolResult.success(
            f"Background task submitted. task_id: {task_id}. "
            f"Use check_background_task to check status."
        )

    async def _execute_tool(
        self, agent_run: AgentRun, tc: dict[str, str], params: dict
    ) -> ToolResult:
        """Execute a regular tool call with approval and permission checks."""
        tool_name = tc["name"]
        tool_call_id = tc["id"]
        tool_args_str = tc["args"]

        tool = self.tool_registry.get(tool_name)
        if tool is None:
            result = ToolResult.failure(f"Unknown tool: {tool_name}")
            await self._store_tool_call(agent_run.id, tool_name, tool_args_str, result, 0)
            return result

        # Unified permission + approval flow
        file_path = params.get("path")
        is_internal = tool.skip_approval or getattr(tool, "always_available", False)
        tool_groups = tool.groups if not is_internal else None

        # 1. Explicit deny by direct name (applies to ALL tools, even internal)
        if self.permission_checker.is_denied(self.agent.role, tool_name, file_path):
            result = ToolResult.failure(
                f"Tool '{tool_name}' denied by permission rules for agent '{self.agent.role}'."
            )
            await self._store_tool_call(
                agent_run.id, tool_name, tool_args_str, result, 0, status="denied"
            )
            return result

        # Before tool hook
        hook_ctx = HookContext(
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"tool_name": tool_name, "params": params},
        )
        hook_result = await self.hook_registry.run(HookPoint.BEFORE_TOOL_CALL, hook_ctx)
        if hook_result.cancelled:
            result = ToolResult.failure(f"Tool call cancelled by hook: {hook_result.reason}")
            await self._store_tool_call(
                agent_run.id, tool_name, tool_args_str, result, 0, status="denied"
            )
            return result

        # 2. skip_approval → skip prompting (deny above still blocks)
        if not tool.skip_approval:
            # 3. Full policy resolution (with group matching for eligible tools)
            policy_str = self.permission_checker.check_normalized(
                self.agent.role, tool_name, file_path, tool_groups
            )

            # 4. Deny is final — no session override can change it
            if policy_str == "deny":
                result = ToolResult.failure(
                    f"Tool '{tool_name}' denied by policy."
                )
                await self._store_tool_call(
                    agent_run.id, tool_name, tool_args_str, result, 0, status="denied"
                )
                return result

            # 5. Session overrides (only for non-deny: auto_approve, always_ask, ask_once)
            policy = self.tool_registry.check_approval(tool_name, policy_str)

            # 6. Act on policy
            if policy in (ApprovalPolicy.ALWAYS_ASK, ApprovalPolicy.ASK_ONCE):
                if not self.callbacks.on_tool_approval_request:
                    result = ToolResult.failure(
                        f"Tool '{tool_name}' requires approval but no approval callback "
                        f"is available."
                    )
                    await self._store_tool_call(
                        agent_run.id, tool_name, tool_args_str, result, 0, status="denied"
                    )
                    return result
                await self.bus.publish(
                    Event.TOOL_APPROVAL_REQUIRED,
                    session_id=agent_run.session_id,
                    agent_role=self.agent.role,
                    data={"tool_name": tool_name, "params": params},
                )
                response = await self.callbacks.on_tool_approval_request(
                    tool_name, tool_call_id, params
                )
                if response == "always":
                    self.tool_registry.set_session_approval(tool_name, True)
                elif response != "y":
                    result = ToolResult.failure(f"Tool '{tool_name}' denied by user.")
                    await self._store_tool_call(
                        agent_run.id, tool_name, tool_args_str, result, 0, status="denied"
                    )
                    if self.callbacks.on_tool_call_end:
                        await self.callbacks.on_tool_call_end(tool_call_id, tool_name, result)
                    return result
            # AUTO_APPROVE → fall through to execute

        # Execute tool
        await self.bus.publish(
            Event.TOOL_CALL_START,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"tool_name": tool_name, "tool_call_id": tool_call_id},
        )

        context = ToolContext(
            session_id=agent_run.session_id,
            agent_run_id=agent_run.id,
            agent_role=self.agent.role,
            working_directory=self.working_directory,
            request_user_input=self.callbacks.request_user_input,
        )

        start = time.monotonic()
        try:
            result = await tool.execute(params, context)
        except Exception as e:
            result = ToolResult.failure(f"Tool execution error: {e}")
        duration_ms = int((time.monotonic() - start) * 1000)

        await self._store_tool_call(agent_run.id, tool_name, tool_args_str, result, duration_ms)

        await self.bus.publish(
            Event.TOOL_CALL_END,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "is_error": result.is_error,
                "duration_ms": duration_ms,
            },
        )

        if self.callbacks.on_tool_call_end:
            await self.callbacks.on_tool_call_end(tool_call_id, tool_name, result)

        # After tool hook
        hook_ctx = HookContext(
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"tool_name": tool_name, "result": result.output[:500]},
        )
        await self.hook_registry.run(HookPoint.AFTER_TOOL_CALL, hook_ctx)

        return result

    async def _store_tool_call(
        self,
        agent_run_id: str,
        tool_name: str,
        params_str: str,
        result: ToolResult,
        duration_ms: int,
        status: str | None = None,
    ) -> None:
        tc = ToolCall(
            agent_run_id=agent_run_id,
            tool_name=tool_name,
            parameters=params_str,
            result=result.output if not result.is_error else result.error,
            status=status or ("error" if result.is_error else "success"),
            duration_ms=duration_ms,
        )
        await self.store.add_tool_call(tc)

    async def _handle_todo_write(
        self, agent_run: AgentRun, tc: dict[str, str], params: dict
    ) -> ToolResult:
        """Handle todo_write tool call - persist todos and publish event."""
        todo_data = params.get("todos", [])

        # Convert to TodoItem objects
        todos = []
        for item in todo_data:
            todo = TodoItem(
                id=item.get("id", ""),
                content=item.get("content", ""),
                status=item.get("status", "pending"),
                priority=item.get("priority", "medium"),
                session_id=agent_run.session_id,
            )
            todos.append(todo)

        # Persist to database (full-sync: replace all todos for this session)
        await self.store.update_todos_batch(agent_run.session_id, todos)

        # Publish event for UI updates
        await self.bus.publish(
            Event.TODO_UPDATED,
            session_id=agent_run.session_id,
            agent_role=self.agent.role,
            data={"todos": [t.to_row() for t in todos]},
        )

        # Format response
        pending = sum(1 for t in todos if t.status == "pending")
        in_progress = sum(1 for t in todos if t.status == "in_progress")
        completed = sum(1 for t in todos if t.status == "completed")
        cancelled = sum(1 for t in todos if t.status == "cancelled")

        summary_parts = []
        if completed:
            summary_parts.append(f"{completed} completed")
        if in_progress:
            summary_parts.append(f"{in_progress} in progress")
        if pending:
            summary_parts.append(f"{pending} pending")
        if cancelled:
            summary_parts.append(f"{cancelled} cancelled")

        summary = f"Todo list updated ({', '.join(summary_parts) if summary_parts else 'empty'})"
        return ToolResult.success(summary)

    async def _handle_todo_read(
        self, agent_run: AgentRun, tc: dict[str, str], params: dict
    ) -> ToolResult:
        """Handle todo_read tool call - fetch todos from database."""
        todos = await self.store.get_session_todos(agent_run.session_id)

        if not todos:
            return ToolResult.success("No todos for this session.")

        # Format for display
        lines = []
        for todo in todos:
            if todo.status == "pending":
                symbol = "[ ]"
            elif todo.status == "in_progress":
                symbol = "[→]"
            elif todo.status == "completed":
                symbol = "[✓]"
            elif todo.status == "cancelled":
                symbol = "[✗]"
            else:
                symbol = "[?]"

            priority_indicator = ""
            if todo.priority == "high":
                priority_indicator = " (!)"
            elif todo.priority == "low":
                priority_indicator = " (↓)"

            lines.append(f"  {symbol} {todo.content}{priority_indicator}")

        display = "\n".join(lines)
        return ToolResult.success(f"Current todo list:\n{display}")

    def _estimate_tokens(self, conversation: list[dict[str, Any]]) -> int:
        """Estimate token count for conversation messages.
        
        Uses a rough estimate of 1 token per 4 characters.
        """
        total = 0
        for msg in conversation:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if content:
                    total += len(content) // 4
            elif isinstance(msg, str):
                total += len(msg) // 4
        return total
