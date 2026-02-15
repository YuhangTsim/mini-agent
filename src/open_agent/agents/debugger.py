"""Debugger agent: full tools with diagnostic focus."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Debugger — a specialist agent for investigating and fixing bugs.

You have full access to read, write, edit files and execute commands.
Your focus is on diagnosing issues and applying fixes.

Guidelines:
- Start by understanding the reported issue
- Read relevant code and error messages
- Run tests to reproduce the problem
- Identify root cause before making changes
- Apply minimal, targeted fixes
- Run tests again to verify the fix
- Use report_result to summarize the issue and fix"""


class DebuggerAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="debugger",
                name="Debugger",
                model="gpt-4o",
                allowed_tools=[
                    "read_file",
                    "write_file",
                    "edit_file",
                    "search_files",
                    "list_files",
                    "execute_command",
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
