"""Skills check section."""

from __future__ import annotations

from typing import Any


def build_skills_section(context: dict[str, Any]) -> str:
    """Build the skills section with available skill names and mandatory check instruction."""
    skills = context.get("skills", [])
    if not skills:
        return ""

    lines = [
        "## Skills",
        "Before responding to any user request, check if any of these skills match:",
        "",
    ]
    for skill in skills:
        lines.append(f"- **{skill['name']}**: {skill['description']}")

    lines.extend([
        "",
        "If a skill matches, call the `skill` tool with the skill name to load its full instructions.",
        "Skills provide specialized knowledge and step-by-step procedures.",
    ])

    return "\n".join(lines)
