"""Delegation section for agents that can delegate."""

from __future__ import annotations

from typing import Any


def build_delegation_section(context: dict[str, Any]) -> str:
    """Build delegation instructions for agents that can delegate to others."""
    agent_config = context["agent_config"]

    if not agent_config.can_delegate_to:
        return ""

    lines = [
        "====",
        "",
        "DELEGATION",
        "",
        "You can delegate tasks to specialist agents using the delegate_task tool.",
        "When delegating:",
        "- Provide a clear, specific description of what the agent should accomplish.",
        "- Choose the most appropriate specialist for the task.",
        "- Wait for the result before proceeding.",
        "",
        "For long-running tasks that don't block your current work, use delegate_background.",
        "Use check_background_task to check on background tasks.",
        "",
        "When your task is complete, use report_result to return your findings.",
    ]

    return "\n".join(lines)
