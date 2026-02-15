"""Tool use section."""

from __future__ import annotations

from typing import Any


def build_tools_section(context: dict[str, Any]) -> str:
    """Build the tool use guidelines section."""
    tools = context.get("tools", [])
    if not tools:
        return ""

    return """====

TOOL USE

You have access to a set of tools that are executed upon the user's approval. Use the provider-native tool-calling mechanism. You must call at least one tool per assistant response when working on a task.

# Tool Use Guidelines

1. Assess what information you already have and what you need to proceed.
2. Choose the most appropriate tool based on the task and tool descriptions.
3. If multiple actions are needed, you may use multiple tools in a single message. Each tool use should be informed by the results of previous tool uses.
4. Always read a file before editing it."""
