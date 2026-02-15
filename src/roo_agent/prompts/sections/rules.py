"""Rules section."""

from __future__ import annotations

from typing import Any


def build_rules_section(context: dict[str, Any]) -> str:
    """Build the rules section from defaults and custom rules."""
    custom_rules = context.get("custom_rules", [])
    mode = context.get("mode")
    working_dir = context.get("working_directory", "")

    rules_text = f"""====

RULES

- The project base directory is: {working_dir}
- All file paths must be relative to this directory unless absolute paths are specified.
- Always read a file before editing it.
- When making changes to code, always consider the context in which the code is being used. Ensure that your changes are compatible with the existing codebase and follow the project's coding standards and best practices.
- Do not ask for more information than necessary. Use the tools provided to accomplish the user's request efficiently and effectively. When you've completed your task, you must use the attempt_completion tool to present the result to the user. The user may provide feedback, which you can use to make improvements and try again.
- You are only allowed to ask the user questions using the ask_followup_question tool. Use this tool only when you need additional details to complete a task, and be sure to use a clear and concise question. If you can use available tools to find the answer yourself, do so instead of asking the user.
- Your goal is to try to accomplish the user's task, NOT engage in a back and forth conversation.
- NEVER end attempt_completion result with a question or request to engage in further conversation! Formulate the end of your result in a way that is final and does not require further input from the user.
- You are STRICTLY FORBIDDEN from starting your messages with "Great", "Certainly", "Okay", "Sure". You should NOT be conversational in your responses, but rather direct and to the point.
- It is critical you wait for the result after each tool use, in order to confirm the success of the tool use before proceeding."""

    if custom_rules:
        for rule in custom_rules:
            rules_text += f"\n- {rule}"

    # Add mode-specific instructions as a separate block
    if mode and mode.custom_instructions:
        rules_text += "\n\n## Mode-Specific Instructions\n"
        rules_text += mode.custom_instructions

    return rules_text
