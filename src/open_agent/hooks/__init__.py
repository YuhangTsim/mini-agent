"""Hook system for intercepting pipeline operations."""

from open_agent.hooks.base import BaseHook, HookContext, HookPoint, HookResult
from open_agent.hooks.registry import HookRegistry

__all__ = ["BaseHook", "HookContext", "HookPoint", "HookResult", "HookRegistry"]
