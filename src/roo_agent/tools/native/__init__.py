"""Native built-in tools."""

from .file_ops import ReadFileTool, WriteFileTool, EditFileTool
from .search import SearchFilesTool, ListFilesTool
from .command import ExecuteCommandTool
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
