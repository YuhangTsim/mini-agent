"""Capabilities section — tells the model what it can do."""

from __future__ import annotations

from typing import Any


def build_capabilities_section(context: dict[str, Any]) -> str:
    """Build the capabilities section."""
    working_dir = context.get("working_directory", "")

    return f"""====

CAPABILITIES

- You have access to tools that let you execute CLI commands on the user's computer, list files, view source code definitions, regex search, read and write files, and ask follow-up questions. These tools help you effectively accomplish a wide range of tasks, such as writing code, making edits or improvements to existing files, understanding the current state of a project, performing system operations, and much more.
- When the user initially gives you a task, you should use the list_files tool to get an overview of the project structure in '{working_dir}'. This provides key insights from directory/file names and file extensions. You can then explore further as needed.
- You can use the execute_command tool to run commands on the user's computer whenever you feel it can help accomplish the user's task. When you need to execute a CLI command, you must provide a clear explanation of what the command does. Prefer to execute complex CLI commands over creating executable scripts, since they are more flexible and easier to run."""
