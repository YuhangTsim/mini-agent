"""Base agent class and agent configuration."""

from __future__ import annotations

from abc import ABC, abstractmethod

from open_agent.config.agents import AgentConfig


class BaseAgent(ABC):
    """Abstract base class for all agents in the pantheon.

    Each agent has a role, an AgentConfig, and knows how to produce
    its system prompt and tool filter.
    """

    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    @property
    def role(self) -> str:
        return self.config.role

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def get_system_prompt(self, context: dict | None = None) -> str:
        """Build the system prompt for this agent.

        Args:
            context: Optional dict with session-level info (working_directory, etc.)
        """
        ...

    def get_tool_filter(self) -> tuple[list[str], list[str]]:
        """Return (allowed_tools, denied_tools) for this agent."""
        return self.config.allowed_tools, self.config.denied_tools

    def can_delegate(self, target_role: str) -> bool:
        """Check if this agent is allowed to delegate to target_role."""
        return target_role in self.config.can_delegate_to

    @property
    def is_leaf(self) -> bool:
        """True if this agent cannot delegate to anyone."""
        return len(self.config.can_delegate_to) == 0
