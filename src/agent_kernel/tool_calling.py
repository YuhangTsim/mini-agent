"""Shared tool-calling reliability helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

TOOL_CALLING_FAILURE_PREFIX = "[tool_calling_non_convergence]"
DEFAULT_INVALID_TOOL_TURN_LIMIT = 2


@dataclass(frozen=True)
class ToolCallingFailure:
    """Structured terminal failure for repeated invalid tool-calling turns."""

    failure_type: str
    invalid_tool_turns: int
    invalid_tool_turn_limit: int

    def to_message(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return (
            f"{TOOL_CALLING_FAILURE_PREFIX} "
            f"Tool-calling did not converge after {self.invalid_tool_turns} consecutive "
            f"invalid tool turns. {payload}"
        )


def build_non_convergence_message(
    *,
    invalid_tool_turns: int,
    invalid_tool_turn_limit: int = DEFAULT_INVALID_TOOL_TURN_LIMIT,
) -> str:
    """Return a stable terminal failure message for repeated invalid tool turns."""
    return ToolCallingFailure(
        failure_type="tool_calling_non_convergence",
        invalid_tool_turns=invalid_tool_turns,
        invalid_tool_turn_limit=invalid_tool_turn_limit,
    ).to_message()
