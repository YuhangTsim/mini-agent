"""Glob-based permission checker for agent × tool × file rules."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PermissionRuleLike(Protocol):
    """Protocol for permission rules - duck typing for compatibility."""

    agent: str
    tool: str
    file: str
    policy: str


class PermissionChecker:
    """Check whether an agent is allowed to use a tool on a file.

    Rules are evaluated first-match-wins. Default policy is "ask".
    """

    def __init__(self, rules: list[Any] | None = None) -> None:
        self._rules = list(rules) if rules else []

    def add_rule(self, rule: Any) -> None:
        self._rules.append(rule)

    def check(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
    ) -> str:
        """Return the policy for this (agent, tool, file) combination.

        Returns: "allow", "deny", or "ask"
        """
        for rule in self._rules:
            if not fnmatch(agent_role, getattr(rule, "agent", "*")):
                continue
            if not fnmatch(tool_name, getattr(rule, "tool", "*")):
                continue
            if file_path is not None and not fnmatch(file_path, getattr(rule, "file", "*")):
                continue
            return getattr(rule, "policy", "ask")

        return "ask"  # default

    def is_allowed(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
    ) -> bool:
        """Convenience: returns True only if policy is "allow"."""
        return self.check(agent_role, tool_name, file_path) == "allow"

    def is_denied(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
    ) -> bool:
        """Convenience: returns True only if policy is "deny"."""
        return self.check(agent_role, tool_name, file_path) == "deny"
