"""Service layer — business logic for all agent operations."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ..config.settings import Settings
from ..core.agent import Agent, AgentCallbacks
from ..core.mode import ModeConfig, get_mode, list_modes
from ..persistence.export import export_task as _export_task
from ..persistence.models import (
    Message, Task, TaskStatus, TokenUsage, new_id,
)
from ..persistence.store import Store
from ..prompts.builder import PromptBuilder
from ..providers.base import BaseProvider
from ..providers.registry import create_provider
from ..skills.manager import SkillsManager
from ..tools.base import ToolRegistry, ToolResult
from ..tools.native import get_all_native_tools
from ..tools.native.skill_tool import SkillTool
from ..tools.agent import get_all_agent_tools
from .events import Event, EventBus, EventType


class AgentService:
    """Central service layer wrapping all agent operations.

    Both the CLI and HTTP API consume this service.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store: Store | None = None
        self.provider: BaseProvider | None = None
        self.registry = ToolRegistry()
        self.skills_manager: SkillsManager | None = None
        self.prompt_builder = PromptBuilder()
        self.event_bus = EventBus()

        # Active task conversations (task_id -> messages list for provider)
        self._conversations: dict[str, list[dict[str, Any]]] = {}

        # Pending approval requests (approval_id -> asyncio.Future)
        self._pending_approvals: dict[str, asyncio.Future] = {}

        # Pending user input requests (input_id -> asyncio.Future)
        self._pending_inputs: dict[str, asyncio.Future] = {}

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        self.settings.ensure_dirs()

        # Store
        self.store = Store(self.settings.db_path)
        await self.store.initialize()

        # Provider
        self.provider = create_provider(self.settings.provider)

        # Skills
        self.skills_manager = SkillsManager(search_dirs=self.settings.skills_dirs)
        self.skills_manager.discover()

        # Tools
        for tool in get_all_native_tools():
            self.registry.register(tool)
        for tool in get_all_agent_tools():
            self.registry.register(tool)
        self.registry.register(SkillTool(skills_manager=self.skills_manager))

    async def shutdown(self) -> None:
        if self.store:
            await self.store.close()

    def _ensure_initialized(self) -> None:
        if self.store is None or self.provider is None:
            raise RuntimeError("AgentService not initialized. Call initialize() first.")

    # --- Task Operations ---

    async def create_task(
        self,
        description: str,
        mode: str = "code",
        parent_id: str | None = None,
        title: str = "",
    ) -> Task:
        self._ensure_initialized()
        root_id = None
        if parent_id:
            parent = await self.store.get_task(parent_id)
            if parent:
                root_id = parent.root_id or parent.id

        task = Task(
            id=new_id(),
            parent_id=parent_id,
            root_id=root_id,
            mode=mode,
            status=TaskStatus.ACTIVE,
            title=title or description[:50],
            description=description,
            working_directory=self.settings.working_directory,
        )
        await self.store.create_task(task)
        self._conversations[task.id] = []

        await self.event_bus.emit(Event(
            type=EventType.TASK_STATUS_CHANGED,
            task_id=task.id,
            data={"status": "active"},
        ))
        return task

    async def send_message(
        self,
        task_id: str,
        content: str,
        callbacks: AgentCallbacks | None = None,
    ) -> str:
        """Send a user message and run the agent loop. Returns final response text."""
        self._ensure_initialized()
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        conversation = self._conversations.get(task_id, [])
        self._conversations[task_id] = conversation

        mode = get_mode(task.mode)
        available_tools = self.registry.get_tools_for_mode(mode.tool_groups)
        skill_summaries = self.skills_manager.get_summaries_for_mode(task.mode)

        system_prompt = self.prompt_builder.build(
            mode=mode,
            task=task,
            settings=self.settings,
            tools=available_tools,
            skills=skill_summaries,
        )

        # Create agent with event bus integration
        effective_callbacks = callbacks or self._make_event_callbacks(task_id)
        agent = Agent(
            provider=self.provider,
            registry=self.registry,
            store=self.store,
            settings=self.settings,
            callbacks=effective_callbacks,
        )

        return await agent.run(
            task=task,
            user_message=content,
            conversation=conversation,
            system_prompt=system_prompt,
        )

    async def get_task(self, task_id: str) -> Task | None:
        self._ensure_initialized()
        return await self.store.get_task(task_id)

    async def list_tasks(
        self,
        parent_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Task]:
        self._ensure_initialized()
        if parent_id is None and status is None:
            return await self.store.get_root_tasks(limit=limit)
        return await self.store.list_tasks(parent_id=parent_id, status=status, limit=limit)

    async def get_messages(self, task_id: str) -> list[Message]:
        self._ensure_initialized()
        return await self.store.get_messages(task_id)

    async def switch_mode(self, task_id: str, mode: str) -> Task:
        self._ensure_initialized()
        get_mode(mode)  # validates
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.mode = mode
        task.updated_at = datetime.utcnow()
        await self.store.update_task(task)
        return task

    async def cancel_task(self, task_id: str) -> Task:
        self._ensure_initialized()
        task = await self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        task.status = TaskStatus.CANCELLED
        task.updated_at = datetime.utcnow()
        await self.store.update_task(task)
        await self.event_bus.emit(Event(
            type=EventType.TASK_STATUS_CHANGED,
            task_id=task_id,
            data={"status": "cancelled"},
        ))
        return task

    async def export_task(self, task_id: str, include_children: bool = False) -> dict:
        self._ensure_initialized()
        return await _export_task(self.store, task_id, include_children)

    def get_modes(self) -> list[ModeConfig]:
        return list_modes()

    # --- Approval / Input Resolution ---

    async def resolve_approval(self, approval_id: str, decision: str) -> None:
        """Resolve a pending tool approval request."""
        future = self._pending_approvals.pop(approval_id, None)
        if future and not future.done():
            future.set_result(decision)

    async def resolve_input(self, input_id: str, answer: str) -> None:
        """Resolve a pending user input request."""
        future = self._pending_inputs.pop(input_id, None)
        if future and not future.done():
            future.set_result(answer)

    # --- Internal ---

    def _make_event_callbacks(self, task_id: str) -> AgentCallbacks:
        """Create callbacks that emit events to the event bus."""
        bus = self.event_bus
        service = self

        async def on_text_delta(text: str) -> None:
            await bus.emit(Event(
                type=EventType.TOKEN_STREAM,
                task_id=task_id,
                data={"text": text},
            ))

        async def on_tool_call_start(call_id: str, name: str, args: str) -> None:
            await bus.emit(Event(
                type=EventType.TOOL_CALL_START,
                task_id=task_id,
                data={"call_id": call_id, "name": name},
            ))

        async def on_tool_call_end(call_id: str, name: str, result: ToolResult) -> None:
            await bus.emit(Event(
                type=EventType.TOOL_CALL_END,
                task_id=task_id,
                data={
                    "call_id": call_id,
                    "name": name,
                    "output": result.output if not result.is_error else result.error,
                    "is_error": result.is_error,
                },
            ))

        async def on_tool_approval_request(
            name: str, call_id: str, params: dict,
        ) -> str:
            """Emit approval event and wait for client response."""
            approval_id = new_id()
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            service._pending_approvals[approval_id] = future

            await bus.emit(Event(
                type=EventType.TOOL_APPROVAL_REQUIRED,
                task_id=task_id,
                data={
                    "approval_id": approval_id,
                    "tool": name,
                    "call_id": call_id,
                    "params": params,
                },
            ))

            # Block until client resolves via POST /api/approvals/{id}
            return await future

        async def request_user_input(
            question: str, suggestions: list[str] | None = None,
        ) -> str:
            """Emit input request event and wait for client response."""
            input_id = new_id()
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            service._pending_inputs[input_id] = future

            await bus.emit(Event(
                type=EventType.USER_INPUT_REQUIRED,
                task_id=task_id,
                data={
                    "input_id": input_id,
                    "question": question,
                    "suggestions": suggestions or [],
                },
            ))

            # Block until client resolves via POST /api/inputs/{id}
            return await future

        async def on_message_end(usage: TokenUsage) -> None:
            await bus.emit(Event(
                type=EventType.MESSAGE_END,
                task_id=task_id,
                data={
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                },
            ))

        return AgentCallbacks(
            on_text_delta=on_text_delta,
            on_tool_call_start=on_tool_call_start,
            on_tool_call_end=on_tool_call_end,
            on_tool_approval_request=on_tool_approval_request,
            request_user_input=request_user_input,
            on_message_end=on_message_end,
        )
