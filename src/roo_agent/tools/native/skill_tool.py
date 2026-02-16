"""Skill loading tool."""

from __future__ import annotations

from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class SkillTool(BaseTool):
    name = "skill"
    groups = ["read", "edit", "command"]
    description = "Load the full instructions for a skill by name."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the skill to load",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    }
    always_available = True

    def __init__(self, skills_manager=None):
        self._skills_manager = skills_manager

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        name = params["name"]

        if self._skills_manager is None:
            return ToolResult.failure("Skills system not initialized")

        skill = self._skills_manager.get(name)
        if skill is None:
            available = [s.name for s in self._skills_manager.all_skills()]
            return ToolResult.failure(
                f"Skill '{name}' not found. Available: {', '.join(available)}"
            )

        return ToolResult.success(
            f"# Skill: {skill.name}\n\n{skill.content}"
        )
