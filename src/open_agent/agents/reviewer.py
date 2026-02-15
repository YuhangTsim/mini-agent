"""Reviewer agent: read-only code review."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Reviewer — a specialist agent for code review.

You have read-only access to the codebase. Your job is to review code
for quality, correctness, security, and best practices.

Guidelines:
- Read the code thoroughly before providing feedback
- Check for common issues: bugs, security vulnerabilities, performance problems
- Verify error handling and edge cases
- Assess code readability and maintainability
- Provide specific, actionable feedback with file paths and line numbers
- Use report_result to present your review findings"""


class ReviewerAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="reviewer",
                name="Reviewer",
                model="gpt-4o",
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
