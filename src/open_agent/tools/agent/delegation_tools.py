"""Delegation tools for multi-agent orchestration.

These tools are used by agents (primarily the orchestrator) to delegate work
to specialist agents, manage background tasks, and report results.
"""

from __future__ import annotations

from typing import Any

from open_agent.tools.base import BaseTool, ToolContext, ToolResult


class DelegateTaskTool(BaseTool):
    """Delegate a task to a specialist agent and wait for the result."""

    name = "delegate_task"
    description = (
        "Delegate a task to a specialist agent. The agent will execute the task and "
        "return the result. This is a blocking call — you will receive the result.\n\n"
        'Example: { "agent_role": "coder", "description": "Add error handling to the login function" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "description": "The role of the agent to delegate to (e.g., 'coder', 'explorer')",
            },
            "description": {
                "type": "string",
                "description": "Clear description of the task for the agent to accomplish",
            },
        },
        "required": ["agent_role", "description"],
        "additionalProperties": False,
    }
    category = "agent"
    skip_approval = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        # This is a placeholder — actual delegation is handled by SessionProcessor
        # which intercepts this tool call and routes to DelegationManager.
        return ToolResult.failure(
            "delegate_task must be handled by SessionProcessor, not executed directly."
        )


class DelegateBackgroundTool(BaseTool):
    """Delegate a task to run in the background (fire-and-forget)."""

    name = "delegate_background"
    description = (
        "Delegate a task to run in the background. Returns immediately with a task_id. "
        "Use check_background_task to check on its status later.\n\n"
        'Example: { "agent_role": "reviewer", "description": "Review the auth module for security issues" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "description": "The role of the agent to delegate to",
            },
            "description": {
                "type": "string",
                "description": "Clear description of the background task",
            },
        },
        "required": ["agent_role", "description"],
        "additionalProperties": False,
    }
    category = "agent"
    skip_approval = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        # Placeholder — handled by SessionProcessor → BackgroundTaskManager
        return ToolResult.failure(
            "delegate_background must be handled by SessionProcessor, not executed directly."
        )


class CheckBackgroundTaskTool(BaseTool):
    """Check the status of a background task."""

    name = "check_background_task"
    description = (
        'Check the status of a background task by its task_id.\n\nExample: { "task_id": "abc-123" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the background task to check",
            },
        },
        "required": ["task_id"],
        "additionalProperties": False,
    }
    category = "agent"
    skip_approval = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        # Placeholder — handled by SessionProcessor → BackgroundTaskManager
        return ToolResult.failure(
            "check_background_task must be handled by SessionProcessor, not executed directly."
        )


class ReportResultTool(BaseTool):
    """Report the final result of a task back to the delegating agent."""

    name = "report_result"
    description = (
        "Report the result of your task. Use this when you have completed the work "
        "assigned to you. The result will be returned to the agent that delegated to you.\n\n"
        'Example: { "result": "Successfully added error handling to login.py" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "result": {
                "type": "string",
                "description": "The result or summary of the completed task",
            },
        },
        "required": ["result"],
        "additionalProperties": False,
    }
    category = "agent"
    skip_approval = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        # Placeholder — SessionProcessor uses this as a signal to end the agent loop
        result = params["result"]
        return ToolResult.success(f"Result reported: {result}")


def get_all_delegation_tools():
    """Return instances of all delegation tools."""
    return [
        DelegateTaskTool(),
        DelegateBackgroundTool(),
        CheckBackgroundTaskTool(),
        ReportResultTool(),
    ]
