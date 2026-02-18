"""Native tools for open-agent."""

from __future__ import annotations

from agent_kernel.tools.native import (
    EditFileTool,
    ExecuteCommandTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)

from open_agent.tools.native.todo import TodoReadTool, TodoWriteTool

__all__ = [
    "ExecuteCommandTool",
    "EditFileTool",
    "ReadFileTool",
    "WriteFileTool",
    "SearchFilesTool",
    "ListFilesTool",
    "TodoReadTool",
    "TodoWriteTool",
    "get_all_native_tools",
]


def get_all_native_tools():
    """Return instances of all native tools for open-agent."""
    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        SearchFilesTool(),
        ListFilesTool(),
        ExecuteCommandTool(),
        TodoReadTool(),
        TodoWriteTool(),
    ]
