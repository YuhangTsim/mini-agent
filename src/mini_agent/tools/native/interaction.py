"""Interaction tools: ask_followup_question."""

from __future__ import annotations

from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class AskFollowupQuestionTool(BaseTool):
    name = "ask_followup_question"
    description = (
        "Ask the user a question to gather additional information needed to complete the task. "
        "Use when you need clarification or more details to proceed effectively. The conversation "
        "will pause until the user responds.\n\n"
        "Parameters:\n"
        "- question: (required) A clear, specific question addressing the information needed\n"
        "- follow_up: (required) A list of 2-4 suggested answers that are complete and actionable"
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Clear, specific question that captures the missing information you need",
            },
            "follow_up": {
                "type": "array",
                "description": "Required list of 2-4 suggested responses; each must be a complete, actionable answer",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Suggested answer the user can pick",
                        },
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 4,
            },
        },
        "required": ["question", "follow_up"],
        "additionalProperties": False,
    }
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        question = params["question"]

        if context.request_user_input is None:
            return ToolResult.failure("User input not available in this context")

        # Format question with suggestions
        suggestions = params.get("follow_up", [])
        display = question
        if suggestions:
            display += "\n\nSuggested answers:"
            for i, s in enumerate(suggestions, 1):
                display += f"\n  {i}. {s['text']}"

        response = await context.request_user_input(display)
        return ToolResult.success(f"User response: {response}")
