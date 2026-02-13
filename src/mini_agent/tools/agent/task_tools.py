"""Agent-level tools: new_task, switch_mode, attempt_completion."""

from __future__ import annotations

from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class NewTaskTool(BaseTool):
    name = "new_task"
    description = (
        "Create a new task instance in the chosen mode using your provided message. "
        "The sub-task runs in its own conversation context and returns a result when complete.\n\n"
        "CRITICAL: This tool MUST be called alone. Do NOT call this tool alongside other tools "
        "in the same message turn. If you need to gather information before delegating, use "
        "other tools in a separate turn first, then call new_task by itself in the next turn."
    )
    parameters = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Slug of the mode to begin the new task in (e.g., code, debug, architect, ask)",
                "enum": ["code", "plan", "ask", "debug"],
            },
            "description": {
                "type": "string",
                "description": "Initial user instructions or context for the new task. Be comprehensive.",
            },
        },
        "required": ["mode", "description"],
        "additionalProperties": False,
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        description = params["description"]
        mode = params.get("mode", "code")
        return ToolResult.success(f"__new_task__:{mode}:{description}")


class SwitchModeTool(BaseTool):
    name = "switch_mode"
    description = (
        "Request to switch to a different mode. This tool allows modes to request switching "
        "to another mode when needed, such as switching to Code mode to make code changes. "
        "The mode switch takes effect immediately for the next iteration."
    )
    parameters = {
        "type": "object",
        "properties": {
            "mode_slug": {
                "type": "string",
                "description": "Slug of the mode to switch to (e.g., code, ask, plan, debug, orchestrator)",
                "enum": ["code", "plan", "ask", "debug", "orchestrator"],
            },
            "reason": {
                "type": "string",
                "description": "Explanation for why the mode switch is needed",
            },
        },
        "required": ["mode_slug", "reason"],
        "additionalProperties": False,
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        mode = params["mode_slug"]
        reason = params.get("reason", "")
        return ToolResult.success(f"__switch_mode__:{mode}:{reason}")


class AttemptCompletionTool(BaseTool):
    name = "attempt_completion"
    description = (
        "After each tool use, the user will respond with the result of that tool use, "
        "i.e. if it succeeded or failed, along with any reasons for failure. Once you've "
        "received the results of tool uses and can confirm that the task is complete, use "
        "this tool to present the result of your work to the user. The user may respond "
        "with feedback if they are not satisfied with the result, which you can use to "
        "make improvements and try again.\n\n"
        "IMPORTANT NOTE: This tool CANNOT be used until you've confirmed from the user "
        "that any previous tool uses were successful. Failure to do so will result in "
        "code corruption and system failure. Before using this tool, you must confirm "
        "that you've received successful results from the user for any previous tool uses. "
        "If not, then DO NOT use this tool.\n\n"
        "Parameters:\n"
        "- result: (required) The result of the task. Formulate this result in a way that "
        "is final and does not require further input from the user. Don't end your result "
        "with questions or offers for further assistance."
    )
    parameters = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "Final result message to deliver to the user once the task is complete",
            },
        },
        "required": ["result"],
        "additionalProperties": False,
    }
    category = "agent"
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        result = params["result"]
        return ToolResult.success(f"__attempt_completion__:{result}")
