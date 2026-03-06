"""Glob-based permission checker for agent × tool × file rules."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Protocol, runtime_checkable

# Legacy policy names are normalized internally
POLICY_ALIASES: dict[str, str] = {
    "allow": "auto_approve",
    "ask": "always_ask",
}


@dataclass
class PermissionRule:
    """A single permission rule: (agent_glob, tool_glob, file_glob) → policy."""

    agent: str = "*"
    tool: str = "*"
    file: str = "*"
    policy: str = "ask"  # allow|deny|ask|auto_approve|always_ask|ask_once


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

    def _matches_tool(
        self, rule_tool: str, tool_name: str, tool_groups: list[str] | None
    ) -> bool:
        """Check if a rule's tool pattern matches a tool name or its groups.

        Direct name match is always tried. Group matching only applies when
        tool_groups is provided (non-None), allowing callers to exclude
        internal tools from group matching by passing tool_groups=None.
        """
        if fnmatch(tool_name, rule_tool):
            return True
        if tool_groups is not None:
            return any(fnmatch(g, rule_tool) for g in tool_groups)
        return False

    def check(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
        tool_groups: list[str] | None = None,
    ) -> str:
        """Return the policy for this (agent, tool, file) combination.

        Returns: "allow", "deny", "ask", "auto_approve", "always_ask", or "ask_once"
        """
        for rule in self._rules:
            if not fnmatch(agent_role, getattr(rule, "agent", "*")):
                continue
            if not self._matches_tool(getattr(rule, "tool", "*"), tool_name, tool_groups):
                continue
            if file_path is not None and not fnmatch(file_path, getattr(rule, "file", "*")):
                continue
            return getattr(rule, "policy", "ask")

        return "ask"  # default

    def check_normalized(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
        tool_groups: list[str] | None = None,
    ) -> str:
        """Return an ApprovalPolicy-compatible policy string.

        Legacy names ("allow", "ask") are normalized to their canonical forms
        ("auto_approve", "always_ask").
        """
        raw = self.check(agent_role, tool_name, file_path, tool_groups)
        return POLICY_ALIASES.get(raw, raw)

    def is_allowed(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
        tool_groups: list[str] | None = None,
    ) -> bool:
        """Convenience: returns True only if policy is "allow"."""
        return self.check(agent_role, tool_name, file_path, tool_groups) == "allow"

    def is_denied(
        self,
        agent_role: str,
        tool_name: str,
        file_path: str | None = None,
        tool_groups: list[str] | None = None,
    ) -> bool:
        """Convenience: returns True only if policy is "deny"."""
        return self.check(agent_role, tool_name, file_path, tool_groups) == "deny"
