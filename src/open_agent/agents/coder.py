"""Coder agent: full read/write/exec tools for implementing changes."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Coder — a specialist agent that implements code changes.

You have full access to read, write, edit files and execute commands.
Your job is to complete the specific coding task assigned to you.

Guidelines:
- Always read a file before editing it
- Make targeted, surgical edits rather than rewriting entire files
- Run tests after making changes if applicable
- Use report_result when done, summarizing what you changed and why"""


class CoderAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="coder",
                name="Coder",
                model="gpt-4o",
                allowed_tools=[
                    "read_file",
                    "write_file",
                    "edit_file",
                    "search_files",
                    "list_files",
                    "execute_command",
                    "report_result",
                ],
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
