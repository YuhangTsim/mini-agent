"""Native built-in tools."""

from open_agent.tools.native.command import ExecuteCommandTool
from open_agent.tools.native.file_ops import EditFileTool, ReadFileTool, WriteFileTool
from open_agent.tools.native.search import ListFilesTool, SearchFilesTool


def get_all_native_tools():
    """Return instances of all native tools."""
    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        SearchFilesTool(),
        ListFilesTool(),
        ExecuteCommandTool(),
    ]
