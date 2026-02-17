"""Tests for agent_kernel.tools.base: ToolRegistry, BaseTool, ToolResult."""

from __future__ import annotations

import pytest

from agent_kernel.tools.base import (
    ApprovalPolicy,
    BaseTool,
    ToolContext,
    ToolRegistry,
    ToolResult,
)


# ---------------------------------------------------------------------------
# Concrete tool implementations for testing
# ---------------------------------------------------------------------------


class ReadTool(BaseTool):
    name = "read_tool"
    description = "Read something"
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}
    groups = ["read"]
    skip_approval = True

    async def execute(self, params, context):
        return ToolResult.success("read result")


class EditTool(BaseTool):
    name = "edit_tool"
    description = "Edit something"
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}
    groups = ["edit"]

    async def execute(self, params, context):
        return ToolResult.success("edit result")


class AlwaysAvailableTool(BaseTool):
    name = "always_tool"
    description = "Always available regardless of mode"
    parameters = {"type": "object", "properties": {}, "additionalProperties": False}
    groups = []
    always_available = True
    skip_approval = True

    async def execute(self, params, context):
        return ToolResult.success("always result")


# ---------------------------------------------------------------------------
# ToolResult tests
# ---------------------------------------------------------------------------


class TestToolResult:
    def test_success_factory(self):
        result = ToolResult.success("some output")
        assert result.output == "some output"
        assert result.error == ""
        assert not result.is_error

    def test_failure_factory(self):
        result = ToolResult.failure("something went wrong")
        assert result.error == "something went wrong"
        assert result.output == ""
        assert result.is_error

    def test_default_values(self):
        result = ToolResult()
        assert result.output == ""
        assert result.error == ""
        assert not result.is_error

    def test_success_empty_string(self):
        result = ToolResult.success("")
        assert result.output == ""
        assert not result.is_error

    def test_failure_preserves_message(self):
        msg = "Error: file not found: /tmp/foo.txt"
        result = ToolResult.failure(msg)
        assert result.error == msg


# ---------------------------------------------------------------------------
# BaseTool tests
# ---------------------------------------------------------------------------


class TestBaseTool:
    def test_get_definition_contains_name(self):
        tool = ReadTool()
        defn = tool.get_definition()
        assert defn["name"] == "read_tool"

    def test_get_definition_contains_description(self):
        tool = ReadTool()
        defn = tool.get_definition()
        assert defn["description"] == "Read something"

    def test_get_definition_contains_parameters(self):
        tool = ReadTool()
        defn = tool.get_definition()
        assert "parameters" in defn
        assert defn["parameters"]["type"] == "object"

    async def test_execute_returns_tool_result(self):
        tool = ReadTool()
        context = ToolContext()
        result = await tool.execute({}, context)
        assert isinstance(result, ToolResult)
        assert not result.is_error


# ---------------------------------------------------------------------------
# ToolRegistry tests
# ---------------------------------------------------------------------------


class TestToolRegistryBasics:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = ReadTool()
        registry.register(tool)
        assert registry.get("read_tool") is tool

    def test_get_unknown_returns_none(self):
        registry = ToolRegistry()
        assert registry.get("does_not_exist") is None

    def test_all_tools_empty(self):
        registry = ToolRegistry()
        assert registry.all_tools() == []

    def test_all_tools_after_registration(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        assert len(registry.all_tools()) == 2

    def test_register_overwrites_same_name(self):
        registry = ToolRegistry()

        class ReadTool2(ReadTool):
            description = "Updated"

        registry.register(ReadTool())
        registry.register(ReadTool2())
        assert registry.get("read_tool").description == "Updated"


class TestToolRegistryAgentFilter:
    def test_allow_list_filters_to_subset(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        tools = registry.get_tools_for_agent(allowed=["read_tool"])
        assert {t.name for t in tools} == {"read_tool"}

    def test_deny_list_excludes_tool(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        tools = registry.get_tools_for_agent(denied=["edit_tool"])
        names = {t.name for t in tools}
        assert "read_tool" in names
        assert "edit_tool" not in names

    def test_no_filter_returns_all(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        assert len(registry.get_tools_for_agent()) == 2

    def test_allow_and_deny_combined(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        registry.register(AlwaysAvailableTool())
        # allow_list takes priority; deny further restricts
        tools = registry.get_tools_for_agent(
            allowed=["read_tool", "always_tool"],
            denied=["read_tool"],
        )
        assert {t.name for t in tools} == {"always_tool"}

    def test_empty_allow_list_means_no_filter(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        # Empty list = no restriction (different from non-empty)
        tools = registry.get_tools_for_agent(allowed=[])
        assert len(tools) == 2


class TestToolRegistryModeFilter:
    def test_group_filter_returns_matching_tools(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        tools = registry.get_tools_for_mode(["read"])
        assert {t.name for t in tools} == {"read_tool"}

    def test_multiple_groups(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(EditTool())
        tools = registry.get_tools_for_mode(["read", "edit"])
        assert {t.name for t in tools} == {"read_tool", "edit_tool"}

    def test_always_available_included_with_no_groups(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(AlwaysAvailableTool())
        tools = registry.get_tools_for_mode([])
        names = {t.name for t in tools}
        assert "always_tool" in names
        assert "read_tool" not in names

    def test_always_available_included_alongside_groups(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        registry.register(AlwaysAvailableTool())
        tools = registry.get_tools_for_mode(["read"])
        names = {t.name for t in tools}
        assert "always_tool" in names
        assert "read_tool" in names

    def test_no_match_returns_empty(self):
        registry = ToolRegistry()
        registry.register(ReadTool())
        tools = registry.get_tools_for_mode(["command"])
        assert tools == []


class TestToolRegistryApproval:
    def test_default_policy_returned(self):
        registry = ToolRegistry()
        policy = registry.check_approval("any_tool", "always_ask")
        assert policy == ApprovalPolicy.ALWAYS_ASK

    def test_auto_approve_policy(self):
        registry = ToolRegistry()
        policy = registry.check_approval("read_tool", "auto_approve")
        assert policy == ApprovalPolicy.AUTO_APPROVE

    def test_ask_once_policy(self):
        registry = ToolRegistry()
        policy = registry.check_approval("write_tool", "ask_once")
        assert policy == ApprovalPolicy.ASK_ONCE

    def test_deny_policy(self):
        registry = ToolRegistry()
        policy = registry.check_approval("dangerous_tool", "deny")
        assert policy == ApprovalPolicy.DENY

    def test_session_approval_overrides_policy(self):
        registry = ToolRegistry()
        registry.set_session_approval("read_tool", True)
        # Even with always_ask policy, session approval overrides
        policy = registry.check_approval("read_tool", "always_ask")
        assert policy == ApprovalPolicy.AUTO_APPROVE

    def test_session_denial_overrides_policy(self):
        registry = ToolRegistry()
        registry.set_session_approval("write_tool", False)
        # Even with auto_approve policy, session denial overrides
        policy = registry.check_approval("write_tool", "auto_approve")
        assert policy == ApprovalPolicy.DENY

    def test_clear_session_approvals(self):
        registry = ToolRegistry()
        registry.set_session_approval("read_tool", True)
        registry.clear_session_approvals()
        # Now falls back to policy
        policy = registry.check_approval("read_tool", "always_ask")
        assert policy == ApprovalPolicy.ALWAYS_ASK

    def test_session_approval_only_for_named_tool(self):
        registry = ToolRegistry()
        registry.set_session_approval("read_tool", True)
        # Other tools are not affected
        policy = registry.check_approval("write_tool", "always_ask")
        assert policy == ApprovalPolicy.ALWAYS_ASK
