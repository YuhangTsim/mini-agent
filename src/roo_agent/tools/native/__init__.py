"""Native built-in tools."""

from agent_kernel.tools.native import (
    EditFileTool,
    ExecuteCommandTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from .todo import UpdateTodoListTool
from .interaction import AskFollowupQuestionTool


def get_all_native_tools():
    """Return instances of all native tools."""
    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        SearchFilesTool(),
        ListFilesTool(),
        ExecuteCommandTool(),
        UpdateTodoListTool(),
        AskFollowupQuestionTool(),
    ]
