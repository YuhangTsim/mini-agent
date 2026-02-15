"""AgentService: frontend-agnostic service layer for the multi-agent system."""

from __future__ import annotations

import asyncio

from open_agent.bus import Event
from open_agent.config import Settings
from open_agent.core.app import OpenAgentApp
from open_agent.core.session import SessionCallbacks
from open_agent.persistence.models import TokenUsage
from open_agent.tools.base import ToolResult


class AgentService:
    """High-level service layer wrapping OpenAgentApp.

    Used by both CLI and HTTP API. Manages event-based communication
    with frontends via the EventBus.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.app = OpenAgentApp(self.settings)
        self.event_bus = self.app.bus

        # Pending approval/input futures for UI interaction
        self._pending_approvals: dict[str, asyncio.Future[str]] = {}
        self._pending_inputs: dict[str, asyncio.Future[str]] = {}

    async def initialize(self) -> None:
        """Initialize the application and all subsystems."""
        await self.app.initialize()
        self.app.set_callbacks(self._make_callbacks())

    async def shutdown(self) -> None:
        """Clean up resources."""
        await self.app.shutdown()

    async def send_message(
        self,
        message: str,
        agent_role: str | None = None,
    ) -> str:
        """Send a user message and get the response.

        Events are published to the EventBus for real-time streaming.
        """
        await self.event_bus.publish(
            Event.SESSION_START,
            session_id=self.app._session.id if self.app._session else "pending",
            agent_role=agent_role or self.settings.default_agent,
            data={"message": message[:100]},
        )

        result = await self.app.process_message(message, agent_role=agent_role)

        await self.event_bus.publish(
            Event.SESSION_END,
            session_id=self.app._session.id if self.app._session else "unknown",
            agent_role=agent_role or self.settings.default_agent,
            data={"result": result[:200] if result else ""},
        )

        return result

    async def resolve_approval(self, approval_id: str, response: str) -> None:
        """Resolve a pending tool approval (from HTTP API)."""
        future = self._pending_approvals.pop(approval_id, None)
        if future and not future.done():
            future.set_result(response)

    async def resolve_input(self, input_id: str, response: str) -> None:
        """Resolve a pending user input request (from HTTP API)."""
        future = self._pending_inputs.pop(input_id, None)
        if future and not future.done():
            future.set_result(response)

    def _make_callbacks(self) -> SessionCallbacks:
        """Create SessionCallbacks that publish events to the bus."""

        async def on_text_delta(text: str) -> None:
            pass  # Handled via bus TOKEN_STREAM in SessionProcessor

        async def on_tool_call_start(call_id: str, name: str, args: str) -> None:
            pass  # Handled via bus TOOL_CALL_START in SessionProcessor

        async def on_tool_call_end(call_id: str, name: str, result: ToolResult) -> None:
            pass  # Handled via bus TOOL_CALL_END in SessionProcessor

        async def on_tool_approval_request(name: str, call_id: str, params: dict) -> str:
            """Wait for approval from UI."""
            from open_agent.persistence.models import new_id

            approval_id = new_id()
            future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
            self._pending_approvals[approval_id] = future

            await self.event_bus.publish(
                Event.TOOL_APPROVAL_REQUIRED,
                session_id=self.app._session.id if self.app._session else "",
                agent_role="",
                data={
                    "approval_id": approval_id,
                    "tool_name": name,
                    "tool_call_id": call_id,
                    "params": params,
                },
            )

            return await future

        async def request_user_input(question: str, suggestions: list[str] | None) -> str:
            """Wait for user input from UI."""
            from open_agent.persistence.models import new_id

            input_id = new_id()
            future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
            self._pending_inputs[input_id] = future

            await self.event_bus.publish(
                Event.TOOL_APPROVAL_REQUIRED,
                session_id=self.app._session.id if self.app._session else "",
                agent_role="",
                data={
                    "type": "user_input",
                    "input_id": input_id,
                    "question": question,
                    "suggestions": suggestions,
                },
            )

            return await future

        async def on_message_end(usage: TokenUsage) -> None:
            pass  # Token tracking handled in SessionProcessor

        return SessionCallbacks(
            on_text_delta=on_text_delta,
            on_tool_call_start=on_tool_call_start,
            on_tool_call_end=on_tool_call_end,
            on_tool_approval_request=on_tool_approval_request,
            request_user_input=request_user_input,
            on_message_end=on_message_end,
        )
