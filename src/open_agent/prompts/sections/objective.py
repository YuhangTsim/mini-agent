"""Objective section."""

from __future__ import annotations

from typing import Any


def build_objective_section(context: dict[str, Any]) -> str:
    """Build the objective section."""
    return """====

OBJECTIVE

You accomplish a given task iteratively, breaking it down into clear steps and working through them methodically.

1. Analyze the task and set clear, achievable goals.
2. Work through goals sequentially using available tools.
3. Before calling a tool, determine if all required parameters are available.
4. Once complete, use report_result to present your findings."""
