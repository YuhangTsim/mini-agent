"""Role definition section based on current mode."""

from __future__ import annotations

from typing import Any

from ...core.mode import list_modes


def build_role_section(context: dict[str, Any]) -> str:
    """Build the role definition section from mode config."""
    mode = context["mode"]

    lines = [mode.role_definition]

    # Add available modes listing so the model knows what modes exist
    all_modes = list_modes()
    lines.append("")
    lines.append("====")
    lines.append("")
    lines.append("MODES")
    lines.append("")
    lines.append("- These are the currently available modes:")
    for m in all_modes:
        description = m.when_to_use if m.when_to_use else m.role_definition.split(".")[0]
        lines.append(f'  * "{m.name}" mode ({m.slug}) - {description}')

    return "\n".join(lines)
