"""Tests for PermissionChecker."""

from agent_kernel.tools.permissions import POLICY_ALIASES, PermissionRule as KernelPermissionRule
from open_agent.config.agents import PermissionRule
from agent_kernel.tools.permissions import PermissionChecker


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


# --- New tests for group matching and policy normalization ---


def test_group_matching_basic():
    """Tool group matching: rule tool='edit' matches tools with group 'edit'."""
    rules = [
        PermissionRule(agent="*", tool="edit", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    # Direct name "edit" doesn't match "write_file", but group does
    assert checker.is_denied("coder", "write_file", tool_groups=["edit"])
    assert checker.is_denied("coder", "edit_file", tool_groups=["edit"])
    # No group match for read tools
    assert not checker.is_denied("coder", "read_file", tool_groups=["read"])


def test_group_matching_glob():
    """Glob patterns work for group matching: 'ed*' matches group 'edit'."""
    rules = [
        PermissionRule(agent="*", tool="ed*", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_denied("coder", "write_file", tool_groups=["edit"])
    assert not checker.is_denied("coder", "write_file", tool_groups=["command"])


def test_group_matching_excluded_when_none():
    """When tool_groups=None, group matching is disabled (internal tools)."""
    rules = [
        PermissionRule(agent="*", tool="edit", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    # tool_groups=None → no group matching, "edit" doesn't match "ask_followup_question"
    assert not checker.is_denied("coder", "ask_followup_question", tool_groups=None)
    # But direct name match still works
    rules2 = [
        PermissionRule(agent="*", tool="ask_followup_question", policy="deny"),
    ]
    checker2 = PermissionChecker(rules2)
    assert checker2.is_denied("coder", "ask_followup_question", tool_groups=None)


def test_direct_name_deny_overrides_groups():
    """Direct name deny applies regardless of tool_groups value."""
    rules = [
        PermissionRule(agent="*", tool="ask_followup_question", policy="deny"),
    ]
    checker = PermissionChecker(rules)
    assert checker.is_denied("coder", "ask_followup_question")
    assert checker.is_denied("coder", "ask_followup_question", tool_groups=None)
    assert checker.is_denied("coder", "ask_followup_question", tool_groups=["read"])


def test_policy_normalization():
    """check_normalized() converts legacy names to canonical forms."""
    rules = [
        PermissionRule(agent="*", tool="read_file", policy="allow"),
        PermissionRule(agent="*", tool="write_file", policy="ask"),
        PermissionRule(agent="*", tool="execute_command", policy="deny"),
        PermissionRule(agent="*", tool="search_files", policy="auto_approve"),
    ]
    checker = PermissionChecker(rules)
    assert checker.check_normalized("coder", "read_file") == "auto_approve"
    assert checker.check_normalized("coder", "write_file") == "always_ask"
    assert checker.check_normalized("coder", "execute_command") == "deny"
    assert checker.check_normalized("coder", "search_files") == "auto_approve"
    # Default is "ask" which normalizes to "always_ask"
    assert checker.check_normalized("coder", "unknown_tool") == "always_ask"


def test_new_policy_values():
    """New policy values (auto_approve, always_ask, ask_once) work directly."""
    rules = [
        PermissionRule(agent="*", tool="read_file", policy="auto_approve"),
        PermissionRule(agent="*", tool="write_file", policy="always_ask"),
        PermissionRule(agent="*", tool="*", policy="ask_once"),
    ]
    checker = PermissionChecker(rules)
    assert checker.check("coder", "read_file") == "auto_approve"
    assert checker.check("coder", "write_file") == "always_ask"
    assert checker.check("coder", "execute_command") == "ask_once"


def test_kernel_permission_rule_dataclass():
    """PermissionRule from kernel works with **dict construction."""
    data = {"agent": "explorer", "tool": "write_file", "file": "*.py", "policy": "deny"}
    rule = KernelPermissionRule(**data)
    assert rule.agent == "explorer"
    assert rule.tool == "write_file"
    assert rule.file == "*.py"
    assert rule.policy == "deny"


def test_kernel_permission_rule_defaults():
    """Kernel PermissionRule has sensible defaults."""
    rule = KernelPermissionRule()
    assert rule.agent == "*"
    assert rule.tool == "*"
    assert rule.file == "*"
    assert rule.policy == "ask"


def test_policy_aliases_constant():
    """POLICY_ALIASES maps legacy names correctly."""
    assert POLICY_ALIASES == {"allow": "auto_approve", "ask": "always_ask"}
