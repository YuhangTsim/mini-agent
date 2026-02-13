"""Rules section."""

from __future__ import annotations

from typing import Any


DEFAULT_RULES = [
    "Be concise and direct.",
    "When editing files, make targeted changes. Don't rewrite entire files unless necessary.",
    "Always read a file before editing it.",
    "Verify your changes work by reading the file after editing.",
    "If you're unsure about something, ask the user using ask_followup_question.",
]


def build_rules_section(context: dict[str, Any]) -> str:
    """Build the rules section from defaults and custom rules."""
    custom_rules = context.get("custom_rules", [])
    mode = context.get("mode")

    rules = list(DEFAULT_RULES)
    if mode and mode.custom_instructions:
        rules.append(mode.custom_instructions)
    rules.extend(custom_rules)

    lines = ["## Rules"]
    for rule in rules:
        lines.append(f"- {rule}")

    return "\n".join(lines)
