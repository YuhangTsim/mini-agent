"""Tests for hooks system."""

from __future__ import annotations

import pytest

from open_agent.hooks.base import (
    BaseHook, HookPoint, HookContext, HookResult,
)
from open_agent.hooks.registry import HookRegistry


class TestHookPoint:
    """Test HookPoint enum."""
    
    def test_hook_point_values(self):
        """Test hook point enum values."""
        assert HookPoint.BEFORE_TOOL_CALL == "before_tool_call"
        assert HookPoint.AFTER_TOOL_CALL == "after_tool_call"
        assert HookPoint.BEFORE_LLM_CALL == "before_llm_call"
        assert HookPoint.AFTER_LLM_CALL == "after_llm_call"
        assert HookPoint.MESSAGE_TRANSFORM == "message_transform"
        assert HookPoint.BEFORE_DELEGATION == "before_delegation"
        assert HookPoint.AFTER_DELEGATION == "after_delegation"


class TestHookContext:
    """Test HookContext."""
    
    def test_default_context(self):
        """Test default hook context."""
        ctx = HookContext()
        assert ctx.session_id == ""
        assert ctx.agent_role == ""
        assert ctx.data is None
    
    def test_context_with_values(self):
        """Test context with values."""
        ctx = HookContext(
            session_id="session-1",
            agent_role="explorer",
            data={"key": "value"},
        )
        assert ctx.session_id == "session-1"
        assert ctx.agent_role == "explorer"
        assert ctx.data == {"key": "value"}


class TestHookResult:
    """Test HookResult."""
    
    def test_default_result(self):
        """Test default hook result."""
        result = HookResult()
        assert result.modified_data is None
        assert result.cancelled is False
        assert result.reason == ""
    
    def test_result_with_modification(self):
        """Test result with modified data."""
        result = HookResult(
            modified_data={"new": "data"},
            cancelled=False,
        )
        assert result.modified_data == {"new": "data"}
    
    def test_result_cancelled(self):
        """Test cancelled result."""
        result = HookResult(
            cancelled=True,
            reason="Operation not allowed",
        )
        assert result.cancelled is True
        assert result.reason == "Operation not allowed"


class ConcreteHook(BaseHook):
    """Concrete hook for testing."""
    
    name = "test-hook"
    hook_point = HookPoint.BEFORE_TOOL_CALL
    priority = 50
    
    def __init__(self, should_cancel=False, modify_data=None):
        self.should_cancel = should_cancel
        self.modify_data = modify_data
    
    async def execute(self, context: HookContext) -> HookResult:
        if self.should_cancel:
            return HookResult(cancelled=True, reason="Cancelled by test")
        if self.modify_data:
            return HookResult(modified_data=self.modify_data)
        return HookResult()


class TestBaseHook:
    """Test BaseHook interface."""
    
    def test_cannot_instantiate_abstract(self):
        """Test that abstract BaseHook cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseHook()
    
    def test_concrete_hook_instantiation(self):
        """Test that concrete hook can be instantiated."""
        hook = ConcreteHook()
        assert hook.name == "test-hook"
        assert hook.hook_point == HookPoint.BEFORE_TOOL_CALL
        assert hook.priority == 50
    
    @pytest.mark.asyncio
    async def test_hook_execute_returns_result(self):
        """Test hook execution returns result."""
        hook = ConcreteHook()
        ctx = HookContext()
        
        result = await hook.execute(ctx)
        
        assert isinstance(result, HookResult)
        assert not result.cancelled
    
    @pytest.mark.asyncio
    async def test_hook_can_cancel(self):
        """Test hook can cancel operation."""
        hook = ConcreteHook(should_cancel=True)
        ctx = HookContext()
        
        result = await hook.execute(ctx)
        
        assert result.cancelled is True
        assert result.reason == "Cancelled by test"
    
    @pytest.mark.asyncio
    async def test_hook_can_modify_data(self):
        """Test hook can modify data."""
        hook = ConcreteHook(modify_data={"modified": True})
        ctx = HookContext()
        
        result = await hook.execute(ctx)
        
        assert result.modified_data == {"modified": True}


class TestHookRegistry:
    """Test HookRegistry."""
    
    @pytest.fixture
    def registry(self):
        return HookRegistry()
    
    def test_registry_creation(self):
        """Test creating hook registry."""
        registry = HookRegistry()
        assert len(registry._hooks) == 0
    
    def test_register_hook(self, registry):
        """Test registering a hook."""
        hook = ConcreteHook()
        registry.register(hook)
        
        hooks = registry.get_hooks(HookPoint.BEFORE_TOOL_CALL)
        assert len(hooks) == 1
        assert hooks[0] == hook
    
    def test_register_sorts_by_priority(self, registry):
        """Test that hooks are sorted by priority."""
        class HighPriorityHook(ConcreteHook):
            priority = 10
        
        class LowPriorityHook(ConcreteHook):
            priority = 100
        
        registry.register(LowPriorityHook())
        registry.register(HighPriorityHook())
        
        hooks = registry.get_hooks(HookPoint.BEFORE_TOOL_CALL)
        # Should be sorted by priority (lower first)
        assert hooks[0].priority == 10
        assert hooks[1].priority == 100
    
    def test_get_hooks_for_different_points(self, registry):
        """Test getting hooks for different points."""
        class ToolHook(ConcreteHook):
            hook_point = HookPoint.BEFORE_TOOL_CALL
        
        class LLMHook(BaseHook):
            name = "llm-hook"
            hook_point = HookPoint.BEFORE_LLM_CALL
            priority = 100
            async def execute(self, context):
                return HookResult()
        
        registry.register(ToolHook())
        registry.register(LLMHook())
        
        tool_hooks = registry.get_hooks(HookPoint.BEFORE_TOOL_CALL)
        assert len(tool_hooks) == 1
        
        llm_hooks = registry.get_hooks(HookPoint.BEFORE_LLM_CALL)
        assert len(llm_hooks) == 1
    
    @pytest.mark.asyncio
    async def test_run_hooks_no_modification(self, registry):
        """Test running hooks that don't modify."""
        registry.register(ConcreteHook())
        
        ctx = HookContext(data={"original": "data"})
        result = await registry.run(HookPoint.BEFORE_TOOL_CALL, ctx)
        
        assert result.cancelled is False
    
    @pytest.mark.asyncio
    async def test_run_hooks_with_modification(self, registry):
        """Test running hooks that modify data."""
        registry.register(ConcreteHook(modify_data={"modified": True}))
        
        ctx = HookContext(data={"original": "data"})
        result = await registry.run(HookPoint.BEFORE_TOOL_CALL, ctx)
        
        assert result.modified_data == {"modified": True}
    
    @pytest.mark.asyncio
    async def test_run_hooks_cancelled(self, registry):
        """Test running hooks that cancel."""
        registry.register(ConcreteHook(should_cancel=True))
        
        ctx = HookContext()
        result = await registry.run(HookPoint.BEFORE_TOOL_CALL, ctx)
        
        assert result.cancelled is True
    
    def test_clear_hooks(self, registry):
        """Test clearing all hooks."""
        registry.register(ConcreteHook())
        assert len(registry.get_hooks(HookPoint.BEFORE_TOOL_CALL)) == 1
        
        registry.clear()
        assert len(registry._hooks) == 0
