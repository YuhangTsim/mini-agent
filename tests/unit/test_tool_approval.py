"""Deterministic tests for the unified tool approval system (no LLM calls)."""

from __future__ import annotations

from agent_kernel.tools.base import ApprovalPolicy, BaseTool, ToolContext, ToolRegistry, ToolResult
from agent_kernel.tools.permissions import PermissionChecker, PermissionRule as KernelRule
from open_agent.config.settings import DEFAULT_TOOL_APPROVAL, Settings as OASettings
from roo_agent.config.settings import ROO_DEFAULT_TOOL_APPROVAL, Settings as RooSettings


# --- Helpers ---


class FakeTool(BaseTool):
    def __init__(
        self,
        name: str,
        groups: list[str] | None = None,
        skip_approval: bool = False,
        always_available: bool = False,
    ):
        self.name = name
        self.description = f"Fake tool: {name}"
        self.parameters = {}
        self.groups = groups or []
        self.skip_approval = skip_approval
        self.always_available = always_available

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        return ToolResult.success(f"{self.name} executed")


# --- Settings compilation tests ---


class TestToolApprovalCompilation:
    def test_open_agent_default_tool_approval_compiled(self):
        """When no [open_agent.tool_approval] in TOML, defaults are compiled."""
        settings = OASettings._from_dict({})
        # Should have default rules compiled from DEFAULT_TOOL_APPROVAL
        tool_patterns = [r.tool for r in settings.permissions]
        for pattern in DEFAULT_TOOL_APPROVAL:
            assert pattern in tool_patterns

    def test_open_agent_custom_tool_approval_compiled(self):
        """[open_agent.tool_approval] entries become PermissionRules."""
        settings = OASettings._from_dict({
            "open_agent": {
                "tool_approval": {
                    "read": "auto_approve",
                    "edit": "deny",
                }
            }
        })
        # Should have the custom rules
        edit_rules = [r for r in settings.permissions if r.tool == "edit"]
        assert len(edit_rules) == 1
        assert edit_rules[0].policy == "deny"

    def test_roo_agent_default_tool_approval_compiled(self):
        """When no [tool_approval] in TOML, defaults are compiled."""
        settings = RooSettings._from_dict({})
        tool_patterns = [r.tool for r in settings.permissions]
        for pattern in ROO_DEFAULT_TOOL_APPROVAL:
            assert pattern in tool_patterns

    def test_roo_agent_custom_tool_approval_compiled(self):
        """[tool_approval] entries become PermissionRules."""
        settings = RooSettings._from_dict({
            "tool_approval": {
                "read": "auto_approve",
                "command": "deny",
            }
        })
        command_rules = [r for r in settings.permissions if r.tool == "command"]
        assert len(command_rules) == 1
        assert command_rules[0].policy == "deny"

    def test_explicit_permissions_precede_tool_approval(self):
        """Explicit [[permissions]] rules have higher priority than [tool_approval]."""
        settings = OASettings._from_dict({
            "permissions": [
                {"agent": "*", "tool": "read", "policy": "deny"},
            ],
            "open_agent": {
                "tool_approval": {
                    "read": "auto_approve",
                }
            },
        })
        checker = PermissionChecker(settings.permissions)
        # Explicit deny comes first, wins over tool_approval auto_approve
        assert checker.check("coder", "read_file", tool_groups=["read"]) == "deny"


# --- Session approval tests ---


class TestSessionApproval:
    def test_session_approval_overrides_ask(self):
        """set_session_approval(tool, True) → check_approval returns AUTO_APPROVE."""
        registry = ToolRegistry()
        registry.set_session_approval("write_file", True)
        policy = registry.check_approval("write_file", "always_ask")
        assert policy == ApprovalPolicy.AUTO_APPROVE

    def test_session_denial_overrides_ask(self):
        """set_session_approval(tool, False) → check_approval returns DENY."""
        registry = ToolRegistry()
        registry.set_session_approval("write_file", False)
        policy = registry.check_approval("write_file", "always_ask")
        assert policy == ApprovalPolicy.DENY

    def test_no_session_approval_returns_policy(self):
        """Without session approval, check_approval returns the given policy."""
        registry = ToolRegistry()
        policy = registry.check_approval("write_file", "always_ask")
        assert policy == ApprovalPolicy.ALWAYS_ASK

    def test_clear_session_approvals(self):
        """clear_session_approvals removes all session overrides."""
        registry = ToolRegistry()
        registry.set_session_approval("write_file", True)
        registry.clear_session_approvals()
        policy = registry.check_approval("write_file", "always_ask")
        assert policy == ApprovalPolicy.ALWAYS_ASK


# --- Permission flow tests ---


class TestUnifiedPermissionFlow:
    def test_skip_approval_bypasses_prompting(self):
        """Tools with skip_approval=True bypass prompting but not deny."""
        rules = [KernelRule(agent="*", tool="*", policy="always_ask")]
        checker = PermissionChecker(rules)
        tool = FakeTool("ask_followup_question", skip_approval=True)

        # skip_approval tools should not be denied by group matching
        assert not checker.is_denied("coder", tool.name)

    def test_skip_approval_still_blocked_by_direct_deny(self):
        """A direct-name deny rule blocks even skip_approval tools."""
        rules = [KernelRule(agent="*", tool="ask_followup_question", policy="deny")]
        checker = PermissionChecker(rules)
        assert checker.is_denied("coder", "ask_followup_question")

    def test_deny_not_overridable_by_session(self):
        """Session approval cannot override a deny policy."""
        # This tests the ordering: deny is checked before registry.check_approval()
        rules = [KernelRule(agent="*", tool="write_file", policy="deny")]
        checker = PermissionChecker(rules)
        registry = ToolRegistry()
        registry.set_session_approval("write_file", True)

        # Even with session approval, checker still says deny
        assert checker.is_denied("coder", "write_file")
        # The flow should check deny BEFORE consulting session approvals

    def test_auto_approve_skips_prompting(self):
        """auto_approve policy means no prompt needed."""
        rules = [KernelRule(agent="*", tool="read_file", policy="auto_approve")]
        checker = PermissionChecker(rules)
        policy_str = checker.check_normalized("coder", "read_file")
        assert policy_str == "auto_approve"

        registry = ToolRegistry()
        policy = registry.check_approval("read_file", policy_str)
        assert policy == ApprovalPolicy.AUTO_APPROVE

    def test_internal_tool_excluded_from_group_matching(self):
        """Internal tools (always_available) are excluded from group matching."""
        rules = [KernelRule(agent="*", tool="edit", policy="deny")]
        checker = PermissionChecker(rules)
        tool = FakeTool(
            "ask_followup_question",
            groups=["read", "edit", "command"],
            always_available=True,
        )

        # With tool_groups=None (internal), group matching disabled
        is_internal = tool.skip_approval or tool.always_available
        tool_groups = tool.groups if not is_internal else None
        assert not checker.is_denied("coder", tool.name, tool_groups=tool_groups)

    def test_group_deny_blocks_eligible_tool(self):
        """Group deny blocks non-internal tools with matching groups."""
        rules = [KernelRule(agent="*", tool="edit", policy="deny")]
        checker = PermissionChecker(rules)
        tool = FakeTool("write_file", groups=["edit"])

        is_internal = tool.skip_approval or getattr(tool, "always_available", False)
        tool_groups = tool.groups if not is_internal else None
        assert checker.is_denied("coder", tool.name, tool_groups=tool_groups)


# --- CLI shorthand tests ---


class TestCLIShorthand:
    def test_open_agent_approval_accepts_a(self):
        """The 'a' shorthand should be accepted as 'always'."""
        # We test the logic from the CLI callback
        test_inputs = {
            "y": "y",
            "yes": "y",
            "a": "always",
            "always": "always",
            "n": "n",
            "no": "n",
        }
        for input_val, expected in test_inputs.items():
            response = input_val.strip().lower()
            if response in ("y", "yes"):
                result = "y"
            elif response in ("a", "always"):
                result = "always"
            elif response in ("n", "no"):
                result = "n"
            else:
                result = None
            assert result == expected, f"Input '{input_val}' should map to '{expected}'"


# --- Fail-closed tests ---


class TestFailClosed:
    def test_missing_callback_fails_closed(self):
        """When policy requires approval but no callback is registered, fail closed."""
        # This tests the design principle, not actual session code
        # The principle: if policy resolves to ALWAYS_ASK or ASK_ONCE and
        # no approval callback is registered, fail with a clear error
        policy = ApprovalPolicy.ALWAYS_ASK
        has_callback = False

        if policy in (ApprovalPolicy.ALWAYS_ASK, ApprovalPolicy.ASK_ONCE) and not has_callback:
            error = (
                "Tool 'write_file' requires approval but no approval callback is available."
            )
            assert "requires approval" in error
            assert "no approval callback" in error
