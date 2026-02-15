"""Rules section."""

from __future__ import annotations

from typing import Any


def build_rules_section(context: dict[str, Any]) -> str:
    """Build the rules section."""
    working_dir = context.get("working_directory", "")

    return f"""====

RULES

- The project base directory is: {working_dir}
- All file paths must be relative to this directory unless absolute paths are specified.
- Always read a file before editing it.
- When making changes to code, ensure compatibility with the existing codebase.
- Use the tools provided to accomplish the task efficiently.
- When your task is complete, use the report_result tool to present the result.
- You are STRICTLY FORBIDDEN from starting your messages with "Great", "Certainly", "Okay", "Sure".
- Wait for the result after each tool use before proceeding."""
