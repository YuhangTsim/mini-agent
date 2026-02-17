"""Deprecated: Use agent_kernel.tools.native instead."""

import warnings

warnings.warn(
    "open_agent.tools.native is deprecated. Use agent_kernel.tools.native instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.tools.native import *  # noqa: F401,F403


def get_all_native_tools():
    """Return instances of all native tools."""
    from agent_kernel.tools.native import (
        ExecuteCommandTool,
        EditFileTool,
        ReadFileTool,
        WriteFileTool,
        SearchFilesTool,
        ListFilesTool,
    )

    return [
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        SearchFilesTool(),
        ListFilesTool(),
        ExecuteCommandTool(),
    ]
