"""Hook registry for managing and executing hooks."""

from __future__ import annotations

import logging
from collections import defaultdict

from open_agent.hooks.base import BaseHook, HookContext, HookPoint, HookResult

logger = logging.getLogger(__name__)


class HookRegistry:
    """Registry that stores and executes hooks by hook point.

    Hooks at the same point are sorted by priority (lower first).
    """

    def __init__(self) -> None:
        self._hooks: dict[HookPoint, list[BaseHook]] = defaultdict(list)

    def register(self, hook: BaseHook) -> None:
        self._hooks[hook.hook_point].append(hook)
        self._hooks[hook.hook_point].sort(key=lambda h: h.priority)

    def unregister(self, hook_name: str) -> None:
        for point, hooks in self._hooks.items():
            self._hooks[point] = [h for h in hooks if h.name != hook_name]

    def get_hooks(self, point: HookPoint) -> list[BaseHook]:
        return list(self._hooks.get(point, []))

    async def run(self, point: HookPoint, context: HookContext) -> HookResult:
        """Run all hooks for a given point in priority order.

        If any hook cancels, stops and returns that result.
        If hooks modify data, the modifications chain through.
        """
        result = HookResult()

        for hook in self._hooks.get(point, []):
            try:
                hook_result = await hook.execute(context)

                if hook_result.cancelled:
                    return hook_result

                if hook_result.modified_data is not None:
                    context.data = hook_result.modified_data
                    result.modified_data = hook_result.modified_data

            except Exception:
                logger.exception("Hook %s failed at %s", hook.name, point)

        return result

    def clear(self) -> None:
        self._hooks.clear()
