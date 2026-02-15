"""Agent configuration schema using Pydantic v2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a single agent in the pantheon."""

    role: str
    name: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    max_iterations: int = 50
    max_delegation_depth: int = 3
    allowed_tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    can_delegate_to: list[str] = Field(default_factory=list)
    file_permissions: list[str] = Field(default_factory=lambda: ["*"])
    role_definition: str = ""

    def model_post_init(self, __context: object) -> None:
        if not self.name:
            self.name = self.role.replace("_", " ").title()


class PermissionRule(BaseModel):
    """A single permission rule: (agent_glob, tool_glob, file_glob) → policy."""

    agent: str = "*"
    tool: str = "*"
    file: str = "*"
    policy: str = "ask"  # allow | deny | ask
