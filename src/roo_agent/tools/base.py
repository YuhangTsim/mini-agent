"""Tool system base: BaseTool, ToolRegistry, ToolContext, approval system."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


class ApprovalPolicy(str, enum.Enum):
    ALWAYS_ASK = "always_ask"
    ASK_ONCE = "ask_once"
    AUTO_APPROVE = "auto_approve"
    DENY = "deny"


@dataclass
class ToolResult:
    """Result of a tool execution."""

    output: str = ""
    error: str = ""
    is_error: bool = False

    @staticmethod
    def success(output: str) -> ToolResult:
        return ToolResult(output=output)

    @staticmethod
    def failure(error: str) -> ToolResult:
        return ToolResult(error=error, is_error=True)


@dataclass
class ToolContext:
    """Context passed to tool execution."""

    task_id: str = ""
    working_directory: str = ""
    mode: str = "code"
    # Callback for tools that need user interaction (e.g., ask_followup_question)
    request_user_input: Callable[[str, list[str] | None], Awaitable[str]] | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    category: str = "native"  # "native" | "extension" | "agent"
    groups: list[str] = []  # Which tool groups include this tool
    always_available: bool = False  # Available regardless of mode
    skip_approval: bool = False  # Skip [y/n/always] approval prompt

    @abstractmethod
    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool with given parameters and context."""
        ...

    def get_definition(self) -> dict[str, Any]:
        """Get the tool definition for LLM function calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Registry that discovers, stores, and filters tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        # Session-level approval overrides (tool_name -> approved)
        self._session_approvals: dict[str, bool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tools_for_mode(self, mode_tool_groups: list[str]) -> list[BaseTool]:
        """Get tools available for a mode's tool groups."""
        result = []
        for tool in self._tools.values():
            if tool.always_available:
                result.append(tool)
            elif any(g in mode_tool_groups for g in tool.groups):
                result.append(tool)
        return result

    def check_approval(self, tool_name: str, policy: str) -> ApprovalPolicy:
        """Determine if a tool call needs approval.

        Returns the effective policy after checking session overrides.
        """
        # Check session overrides first
        if tool_name in self._session_approvals:
            return ApprovalPolicy.AUTO_APPROVE if self._session_approvals[tool_name] else ApprovalPolicy.DENY

        return ApprovalPolicy(policy)

    def set_session_approval(self, tool_name: str, approved: bool) -> None:
        """Set a session-level approval override (from 'always' response)."""
        self._session_approvals[tool_name] = approved

    def clear_session_approvals(self) -> None:
        self._session_approvals.clear()
