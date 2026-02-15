"""Tests for PermissionChecker."""

from open_agent.config.agents import PermissionRule
from open_agent.tools.permissions import PermissionChecker


def test_default_policy_is_ask():
    checker = PermissionChecker()
    assert checker.check("coder", "read_file") == "ask"


def test_deny_env_files():
    rules = [
        PermissionRule(agent="*", tool="*", file=".env*", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_denied("coder", "read_file", ".env")
    assert checker.is_denied("coder", "read_file", ".env.local")
    assert not checker.is_denied("coder", "read_file", "main.py")


def test_allow_read_for_all():
    rules = [
        PermissionRule(agent="*", tool="read_file", file="*", policy="allow"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_allowed("coder", "read_file", "anything.py")
    assert checker.is_allowed("explorer", "read_file")
    assert not checker.is_allowed("coder", "write_file", "anything.py")


def test_first_match_wins():
    rules = [
        PermissionRule(agent="*", tool="*", file=".env*", policy="deny"),
        PermissionRule(agent="*", tool="read_file", file="*", policy="allow"),
        PermissionRule(agent="*", tool="*", file="*", policy="ask"),
    ]
    checker = PermissionChecker(rules)
    # .env is denied even for read_file (first rule matches)
    assert checker.is_denied("coder", "read_file", ".env")
    # Normal read is allowed (second rule)
    assert checker.is_allowed("coder", "read_file", "main.py")
    # Write falls through to ask (third rule)
    assert checker.check("coder", "write_file", "main.py") == "ask"


def test_agent_specific_rule():
    rules = [
        PermissionRule(agent="explorer", tool="write_file", policy="deny"),
        PermissionRule(agent="*", tool="*", policy="allow"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_denied("explorer", "write_file")
    assert checker.is_allowed("coder", "write_file")


def test_glob_patterns():
    rules = [
        PermissionRule(agent="*", tool="execute_*", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_denied("coder", "execute_command")
    assert not checker.is_denied("coder", "read_file")


def test_add_rule():
    checker = PermissionChecker()
    assert checker.check("coder", "read_file") == "ask"
    checker.add_rule(PermissionRule(agent="*", tool="*", policy="allow"))
    assert checker.check("coder", "read_file") == "allow"
