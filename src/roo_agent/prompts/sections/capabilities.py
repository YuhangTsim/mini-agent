"""Capabilities section — tells the model what it can do."""

from __future__ import annotations

from typing import Any


def build_capabilities_section(context: dict[str, Any]) -> str:
    """Build the capabilities section."""
    return """====

CAPABILITIES

- You have access to tools that let you execute CLI commands on the user's computer, list files, view source code definitions, regex search, read and write files, and ask follow-up questions. These tools help you effectively accomplish a wide range of tasks, such as writing code, making edits or improvements to existing files, understanding the current state of a project, performing system operations, and much more.
- When the user initially gives you a task, a recursive list of all filepaths in the current workspace directory will be included in environment_details. This provides an overview of the project file structure.
- You can use the execute_command tool to run commands on your computer whenever you feel it can help accomplish the user's task."""
