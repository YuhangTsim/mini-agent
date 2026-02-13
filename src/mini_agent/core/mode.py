"""Mode definitions and switching."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModeConfig:
    slug: str
    name: str
    role_definition: str
    when_to_use: str
    tool_groups: list[str] = field(default_factory=list)
    file_restrictions: dict[str, str] = field(default_factory=dict)
    custom_instructions: str = ""


# Built-in mode definitions
BUILTIN_MODES: dict[str, ModeConfig] = {
    "code": ModeConfig(
        slug="code",
        name="Code",
        role_definition=(
            "You are a skilled software engineer. You can read, write, and edit files, "
            "search codebases, and execute commands to implement solutions."
        ),
        when_to_use="For writing, editing, and implementing code changes.",
        tool_groups=["read", "edit", "command"],
    ),
    "plan": ModeConfig(
        slug="plan",
        name="Plan",
        role_definition=(
            "You are a technical architect. You analyze requirements, design solutions, "
            "and create implementation plans. You can read code and edit markdown files only."
        ),
        when_to_use="For planning and designing before implementation.",
        tool_groups=["read", "edit"],
        file_restrictions={"edit": r"\.(md|txt)$"},
    ),
    "ask": ModeConfig(
        slug="ask",
        name="Ask",
        role_definition=(
            "You are a knowledgeable assistant. You can read files and answer questions "
            "about the codebase, but you cannot modify anything."
        ),
        when_to_use="For asking questions and getting explanations without changes.",
        tool_groups=["read"],
    ),
    "debug": ModeConfig(
        slug="debug",
        name="Debug",
        role_definition=(
            "You are a debugging specialist. You systematically investigate issues, "
            "read logs, run diagnostics, and fix bugs."
        ),
        when_to_use="For troubleshooting and fixing bugs.",
        tool_groups=["read", "edit", "command"],
    ),
    "orchestrator": ModeConfig(
        slug="orchestrator",
        name="Orchestrator",
        role_definition=(
            "You are a task orchestrator. You break complex tasks into sub-tasks "
            "and delegate them to appropriate modes. You do not directly edit files."
        ),
        when_to_use="For complex tasks that need to be broken into sub-tasks.",
        tool_groups=[],  # Only agent tools (always_available)
    ),
}


def get_mode(slug: str) -> ModeConfig:
    """Get a mode by slug. Raises KeyError if not found."""
    if slug not in BUILTIN_MODES:
        raise KeyError(f"Unknown mode: {slug}. Available: {list(BUILTIN_MODES.keys())}")
    return BUILTIN_MODES[slug]


def list_modes() -> list[ModeConfig]:
    return list(BUILTIN_MODES.values())
