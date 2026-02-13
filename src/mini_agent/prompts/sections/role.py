"""Role definition section based on current mode."""

from __future__ import annotations

from typing import Any


def build_role_section(context: dict[str, Any]) -> str:
    """Build the role definition section from mode config."""
    mode = context["mode"]
    return mode.role_definition
