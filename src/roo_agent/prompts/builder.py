"""Dynamic prompt composer that assembles sections into a system prompt."""

from __future__ import annotations

from typing import Any

from ..core.mode import ModeConfig
from ..persistence.models import Task
from ..config.settings import Settings
from ..tools.base import BaseTool
from .sections.role import build_role_section
from .sections.tools import build_tools_section
from .sections.capabilities import build_capabilities_section
from .sections.skills import build_skills_section
from .sections.rules import build_rules_section
from .sections.objective import build_objective_section
from .sections.system_info import build_system_info_section


class PromptBuilder:
    """Assembles system prompts from sections.

    Section order follows Roo's proven layout:
      Role → Tool Use → Capabilities → Modes (in role) → Skills → Rules → System Info → Objective → Custom Instructions
    """

    def __init__(self):
        # Ordered list of section builders
        self._sections = [
            build_role_section,
            build_tools_section,
            build_capabilities_section,
            build_skills_section,
            build_rules_section,
            build_system_info_section,
            build_objective_section,
        ]

    def build(
        self,
        mode: ModeConfig,
        task: Task,
        settings: Settings,
        tools: list[BaseTool] | None = None,
        skills: list[dict[str, str]] | None = None,
        custom_rules: list[str] | None = None,
    ) -> str:
        """Build the complete system prompt."""
        context: dict[str, Any] = {
            "mode": mode,
            "task": task,
            "settings": settings,
            "working_directory": task.working_directory or settings.working_directory,
            "tools": tools or [],
            "skills": skills or [],
            "custom_rules": custom_rules or [],
        }

        parts = []
        for section_fn in self._sections:
            section = section_fn(context)
            if section:
                parts.append(section)

        return "\n\n".join(parts)
