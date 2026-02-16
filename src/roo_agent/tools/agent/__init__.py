"""Agent-level tools (task management)."""

from .task_tools import NewTaskTool, SwitchModeTool, AttemptCompletionTool


def get_all_agent_tools():
    """Return instances of all agent tools."""
    return [
        NewTaskTool(),
        SwitchModeTool(),
        AttemptCompletionTool(),
    ]
