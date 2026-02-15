"""Agent registry for lookup by role."""

from __future__ import annotations

from open_agent.agents.base import BaseAgent


class AgentRegistry:
    """Registry of all available agents, indexed by role."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.role] = agent

    def get(self, role: str) -> BaseAgent | None:
        return self._agents.get(role)

    def get_required(self, role: str) -> BaseAgent:
        agent = self._agents.get(role)
        if agent is None:
            raise KeyError(f"No agent registered for role: {role}")
        return agent

    def all_agents(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def roles(self) -> list[str]:
        return list(self._agents.keys())
