"""Hook system base: BaseHook, HookPoint."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class HookPoint(str, enum.Enum):
    """Points in the pipeline where hooks can intercept."""

    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"
    MESSAGE_TRANSFORM = "message_transform"
    BEFORE_DELEGATION = "before_delegation"
    AFTER_DELEGATION = "after_delegation"


@dataclass
class HookContext:
    """Context passed to hooks."""

    session_id: str = ""
    agent_role: str = ""
    data: dict[str, Any] | None = None


@dataclass
class HookResult:
    """Result from a hook execution.

    If modified_data is set, it replaces the original data.
    If cancelled is True, the operation is skipped.
    """

    modified_data: dict[str, Any] | None = None
    cancelled: bool = False
    reason: str = ""


class BaseHook(ABC):
    """Abstract base class for hooks."""

    name: str = ""
    hook_point: HookPoint = HookPoint.BEFORE_TOOL_CALL
    priority: int = 100  # lower = runs first

    @abstractmethod
    async def execute(self, context: HookContext) -> HookResult:
        """Execute the hook. Return HookResult to modify or cancel the operation."""
        ...
