"""Agent-level tools: new_task, switch_mode, attempt_completion."""

from __future__ import annotations

from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class NewTaskTool(BaseTool):
    name = "new_task"
    description = (
        "Create a new sub-task to delegate work. The sub-task runs in its own context "
        "and returns a result to the parent task when complete."
    )
    parameters = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "What the sub-task should accomplish",
            },
            "mode": {
                "type": "string",
                "description": "The mode for the sub-task (code, plan, ask, debug). Default: code.",
                "enum": ["code", "plan", "ask", "debug"],
            },
        },
        "required": ["description"],
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        description = params["description"]
        mode = params.get("mode", "code")
        # The actual task creation is handled by the agent loop / session layer.
        # This tool returns a signal that the session should create a child task.
        return ToolResult.success(
            f"__new_task__:{mode}:{description}"
        )


class SwitchModeTool(BaseTool):
    name = "switch_mode"
    description = "Switch the current task to a different mode (e.g., from code to plan)."
    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "The mode to switch to",
                "enum": ["code", "plan", "ask", "debug", "orchestrator"],
            },
            "reason": {
                "type": "string",
                "description": "Why you're switching modes",
            },
        },
        "required": ["mode"],
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        mode = params["mode"]
        reason = params.get("reason", "")
        return ToolResult.success(f"__switch_mode__:{mode}:{reason}")


class AttemptCompletionTool(BaseTool):
    name = "attempt_completion"
    description = (
        "Indicate that the current task is complete. Provide a summary of what was accomplished. "
        "The result will be returned to the parent task if this is a sub-task."
    )
    parameters = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "Summary of what was accomplished",
            },
        },
        "required": ["result"],
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        result = params["result"]
        return ToolResult.success(f"__attempt_completion__:{result}")
