"""Role definition section based on agent config."""

from __future__ import annotations

from typing import Any


def build_role_section(context: dict[str, Any]) -> str:
    """Build the role definition section from agent config."""
    agent_config = context["agent_config"]

    lines = []

    if agent_config.role_definition:
        lines.append(agent_config.role_definition)
    else:
        lines.append(f"You are the {agent_config.name} agent. Your role is '{agent_config.role}'.")

    # If this agent can delegate, list available delegates
    if agent_config.can_delegate_to:
        lines.append("")
        lines.append("You can delegate tasks to the following specialist agents:")
        for role in agent_config.can_delegate_to:
            lines.append(f"  - {role}")

    return "\n".join(lines)
