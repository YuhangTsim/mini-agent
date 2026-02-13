"""Rules section."""

from __future__ import annotations

from typing import Any


DEFAULT_RULES = [
    "Be concise and direct.",
    "When editing files, make targeted changes. Don't rewrite entire files unless necessary.",
    "Always read a file before editing it.",
    "Verify your changes work by reading the file after editing.",
    "If you're unsure about something, ask the user using ask_followup_question.",
    "When you use tools to gather information, always summarize what you found in your response to the user.",
]


def build_rules_section(context: dict[str, Any]) -> str:
    """Build the rules section from defaults and custom rules."""
    custom_rules = context.get("custom_rules", [])
    mode = context.get("mode")

    rules = list(DEFAULT_RULES)
    rules.extend(custom_rules)

    lines = ["## Rules"]
    for rule in rules:
        lines.append(f"- {rule}")

    # Add mode-specific instructions as a separate block
    if mode and mode.custom_instructions:
        lines.append("")
        lines.append("## Mode-Specific Instructions")
        lines.append(mode.custom_instructions)

    return "\n".join(lines)
