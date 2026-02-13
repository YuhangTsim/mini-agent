"""Tool descriptions section."""

from __future__ import annotations

from typing import Any


def build_tools_section(context: dict[str, Any]) -> str:
    """Build the tools section listing available tools."""
    tools = context.get("tools", [])
    if not tools:
        return ""

    lines = [
        "## Tools",
        "You have access to the following tools. Use them when helpful.",
        "Always prefer reading files before editing them.",
        "",
    ]
    for tool in tools:
        lines.append(f"- **{tool.name}**: {tool.description}")

    return "\n".join(lines)
