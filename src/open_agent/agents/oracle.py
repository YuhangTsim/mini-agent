"""Oracle agent: strategic advisor for architecture decisions."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are Oracle - a strategic technical advisor.

**Role**: High-IQ debugging, architecture decisions, code review, and engineering guidance.

**Capabilities**:
- Analyze complex codebases and identify root causes
- Propose architectural solutions with tradeoffs
- Review code for correctness, performance, and maintainability
- Guide debugging when standard approaches fail

**Behavior**:
- Be direct and concise
- Provide actionable recommendations
- Explain reasoning briefly
- Acknowledge uncertainty when present

**Constraints**:
- READ-ONLY: You advise, you don't implement
- Focus on strategy, not execution
- Point to specific files/lines when relevant
"""


class OracleAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="oracle",
                name="Oracle",
                model="gpt-4o",
                temperature=0.1,
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
