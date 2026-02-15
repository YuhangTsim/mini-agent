"""Dynamic prompt composer that assembles sections into a system prompt."""

from __future__ import annotations

from typing import Any

from open_agent.config.agents import AgentConfig
from open_agent.prompts.sections.delegation import build_delegation_section
from open_agent.prompts.sections.objective import build_objective_section
from open_agent.prompts.sections.role import build_role_section
from open_agent.prompts.sections.rules import build_rules_section
from open_agent.prompts.sections.system_info import build_system_info_section
from open_agent.prompts.sections.tools import build_tools_section
from open_agent.tools.base import BaseTool


class PromptBuilder:
    """Assembles system prompts from sections.

    Section order: Role → Tools → Delegation → Rules → System Info → Objective
    """

    def __init__(self) -> None:
        self._sections = [
            build_role_section,
            build_tools_section,
            build_delegation_section,
            build_rules_section,
            build_system_info_section,
            build_objective_section,
        ]

    def build(
        self,
        agent_config: AgentConfig,
        working_directory: str = "",
        tools: list[BaseTool] | None = None,
    ) -> str:
        """Build the complete system prompt for an agent."""
        context: dict[str, Any] = {
            "agent_config": agent_config,
            "working_directory": working_directory,
            "tools": tools or [],
        }

        parts = []
        for section_fn in self._sections:
            section = section_fn(context)
            if section:
                parts.append(section)

        return "\n\n".join(parts)
