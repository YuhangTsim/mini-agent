"""Orchestrator agent: delegates tasks, doesn't implement directly."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent
from open_agent.config.agents import AgentConfig

ROLE_DEFINITION = """\
You are the Orchestrator — the top-level coordinator for a multi-agent system.

Your job is to:
1. Understand the user's request
2. Break it into subtasks
3. Delegate each subtask to the most appropriate specialist agent
4. Synthesize the results into a coherent response

You do NOT implement solutions directly. You delegate to specialists:
- **coder**: For writing, editing, or modifying code files
- **explorer**: For reading files, searching code, understanding structure
- **planner**: For creating implementation plans and technical documents
- **debugger**: For investigating bugs, running tests, diagnosing issues
- **reviewer**: For code review, security audit, best practices check

Guidelines:
- For simple questions that just need reading files, delegate to explorer
- For code changes, delegate to coder with a clear description of what to change
- For complex tasks, first delegate to planner, then use the plan to delegate to coder
- You can run multiple delegations sequentially or use background tasks for independent work
- Always synthesize results before reporting back to the user"""


class OrchestratorAgent(BaseAgent):
    def __init__(self, config: AgentConfig | None = None) -> None:
        if config is None:
            config = AgentConfig(
                role="orchestrator",
                name="Orchestrator",
                model="gpt-4o",
                temperature=0.0,
                allowed_tools=[
                    "delegate_task",
                    "delegate_background",
                    "check_background_task",
                    "report_result",
                ],
                can_delegate_to=["coder", "explorer", "planner", "debugger", "reviewer"],
                role_definition=ROLE_DEFINITION,
            )
        else:
            if not config.role_definition:
                config.role_definition = ROLE_DEFINITION
        super().__init__(config)

    def get_system_prompt(self, context: dict | None = None) -> str:
        from open_agent.prompts.builder import PromptBuilder

        builder = PromptBuilder()
        return builder.build(
            agent_config=self.config,
            working_directory=(context or {}).get("working_directory", ""),
        )
