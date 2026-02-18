"""Custom instructions section — mode-specific and user-defined instructions."""

from __future__ import annotations

from typing import Any


def build_custom_instructions_section(context: dict[str, Any]) -> str:
    """Build the custom instructions section.
    
    This section is placed at the very end of the system prompt and contains:
    - Mode-specific instructions from the mode config
    - Any user-defined custom rules
    """
    mode = context.get("mode")
    
    if not mode or not mode.custom_instructions:
        return ""
    
    return f"""====

USER'S CUSTOM INSTRUCTIONS

The following additional instructions are provided by the user for this mode:

{mode.custom_instructions}"""
