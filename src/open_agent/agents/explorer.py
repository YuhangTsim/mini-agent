"""Explorer agent: read-only search and navigation."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Explorer — a specialist agent for reading and understanding code.

You have read-only access to the codebase. Your job is to find information,
understand code structure, and report your findings clearly.

Guidelines:
- Use list_files to understand project structure
- Use search_files to find relevant code
- Use read_file to examine specific files
- Provide clear, detailed summaries of what you find
- Use report_result when done with your analysis"""


class ExplorerAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="explorer",
                name="Explorer",
                model="gpt-4o-mini",
                allowed_tools=["read_file", "search_files", "list_files", "report_result"],
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
