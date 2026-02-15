"""Glob-based permission checker for agent × tool × file rules."""

from __future__ import annotations

from fnmatch import fnmatch

from open_agent.config.agents import PermissionRule


class PermissionChecker:
    """Check whether an agent is allowed to use a tool on a file.

    Rules are evaluated first-match-wins. Default policy is "ask".
    """

    def __init__(self, rules: list[PermissionRule] | None = None) -> None:
        self._rules = list(rules) if rules else []

    def add_rule(self, rule: PermissionRule) -> None:
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
            if not fnmatch(agent_role, rule.agent):
                continue
            if not fnmatch(tool_name, rule.tool):
                continue
            if file_path is not None and not fnmatch(file_path, rule.file):
                continue
            return rule.policy

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
