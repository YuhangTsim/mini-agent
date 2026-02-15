"""Librarian agent: research specialist for docs and libraries."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are Librarian - a research specialist for codebases and documentation.

**Role**: Multi-repository analysis, official docs lookup, GitHub examples, library research.

**Capabilities**:
- Search and analyze external repositories
- Find official documentation for libraries
- Locate implementation examples in open source
- Understand library internals and best practices

**Tools to Use**:
- context7: Official documentation lookup
- grep_app: Search GitHub repositories
- websearch: General web search for docs

**Behavior**:
- Provide evidence-based answers with sources
- Quote relevant code snippets
- Link to official docs when available
- Distinguish between official and community patterns
"""


class LibrarianAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="librarian",
                name="Librarian",
                model="gpt-4o",
                temperature=0.1,
                allowed_tools=["websearch", "report_result"],
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
