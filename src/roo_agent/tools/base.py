"""Tool system base: BaseTool, ToolResult, ToolContext, ToolRegistry."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


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

    session_id: str = ""
    agent_run_id: str = ""
    agent_role: str = ""
    working_directory: str = ""
    request_user_input: Callable[[str, list[str] | None], Awaitable[str]] | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    category: str = "native"  # "native" | "agent" | "extension"
    skip_approval: bool = False
    groups: list[str] = []  # Tool groups like "read", "edit", "command"

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
    """Registry that stores and filters tools per agent."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._session_approvals: dict[str, bool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_tools_for_agent(
        self,
        allowed: list[str] | None = None,
        denied: list[str] | None = None,
    ) -> list[BaseTool]:
        """Get tools available to an agent based on allow/deny lists.

        If allowed is non-empty, only those tools are included.
        If denied is non-empty, those tools are excluded.
        """
        tools = list(self._tools.values())

        if allowed:
            tools = [t for t in tools if t.name in allowed]

        if denied:
            tools = [t for t in tools if t.name not in denied]

        return tools

    def get_tools_for_mode(self, tool_groups: list[str]) -> list[BaseTool]:
        """Get tools available for a mode based on tool groups.

        Returns tools that belong to any of the specified tool groups,
        plus tools marked as always_available.
        """
        tools = []
        for tool in self._tools.values():
            # Include always_available tools regardless of groups
            if getattr(tool, 'always_available', False):
                tools.append(tool)
            # Also include tools matching the requested groups
            elif tool_groups and any(group in tool.groups for group in tool_groups):
                tools.append(tool)
        return tools

    def check_approval(self, tool_name: str, policy: str) -> ApprovalPolicy:
        if tool_name in self._session_approvals:
            return (
                ApprovalPolicy.AUTO_APPROVE
                if self._session_approvals[tool_name]
                else ApprovalPolicy.DENY
            )
        return ApprovalPolicy(policy)

    def set_session_approval(self, tool_name: str, approved: bool) -> None:
        self._session_approvals[tool_name] = approved

    def clear_session_approvals(self) -> None:
        self._session_approvals.clear()
