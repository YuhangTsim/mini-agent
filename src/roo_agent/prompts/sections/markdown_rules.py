"""Markdown formatting rules section."""

from __future__ import annotations

from typing import Any


def build_markdown_rules_section(context: dict[str, Any]) -> str:
    """Build the markdown rules section with clickable link requirements."""
    return """====

MARKDOWN RULES

ALL responses MUST show ANY `language construct` OR filename reference as clickable, exactly as [`filename OR language.declaration()`](relative/file/path.ext:line); line is required for `syntax` and optional for filename links. This applies to ALL markdown responses and ALSO those in attempt_completion"""
