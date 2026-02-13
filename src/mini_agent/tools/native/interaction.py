"""Interaction tools: ask_followup_question."""

from __future__ import annotations

from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class AskFollowupQuestionTool(BaseTool):
    name = "ask_followup_question"
    description = (
        "Ask the user a clarifying question. Use this when you need more information "
        "before proceeding. The conversation will pause until the user responds."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user",
            },
        },
        "required": ["question"],
    }
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        question = params["question"]

        if context.request_user_input is None:
            return ToolResult.failure("User input not available in this context")

        response = await context.request_user_input(question)
        return ToolResult.success(f"User response: {response}")
