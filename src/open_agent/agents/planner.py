"""Planner agent: creates implementation plans, can write markdown."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Planner — a specialist agent for creating implementation plans.

You can read the codebase to understand context and write markdown files
to document plans. You can also delegate to Explorer for research.

Guidelines:
- Read relevant code to understand the current architecture
- Create clear, actionable implementation plans
- Break complex tasks into ordered steps
- Identify risks and dependencies
- Write plans as markdown files when requested
- Use report_result to present your plan"""


class PlannerAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="planner",
                name="Planner",
                model="gpt-4o",
                temperature=0.2,
                allowed_tools=[
                    "read_file",
                    "search_files",
                    "list_files",
                    "write_file",
                    "delegate_task",
                    "report_result",
                ],
                can_delegate_to=["explorer"],
                role_definition=ROLE_DEFINITION,
            )
        else:
            if not config.role_definition:
                config.role_definition = ROLE_DEFINITION
        super().__init__(config)

    def get_system_prompt(self, context: dict | None = None) -> str:
        from open_agent.prompts.builder import PromptBuilder

        return PromptBuilder().build(
            agent_config=self.config,
            working_directory=(context or {}).get("working_directory", ""),
        )
