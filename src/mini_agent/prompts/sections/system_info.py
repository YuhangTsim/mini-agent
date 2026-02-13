"""System information section."""

from __future__ import annotations

import platform
from datetime import datetime
from typing import Any


def build_system_info_section(context: dict[str, Any]) -> str:
    """Build system information section."""
    task = context.get("task")
    working_dir = context.get("working_directory", "")
    mode = context.get("mode")

    lines = [
        "## System Information",
        f"- OS: {platform.system()} {platform.release()}",
        f"- Working directory: {working_dir}",
        f"- Current date: {datetime.utcnow().strftime('%Y-%m-%d')}",
    ]

    if mode:
        lines.append(f"- Current mode: {mode.slug} ({mode.name})")

    if task and task.todo_list:
        lines.append("")
        lines.append("## Current Todo List")
        for item in task.todo_list:
            check = "[x]" if item.done else "[ ]"
            lines.append(f"- {check} {item.text}")

    return "\n".join(lines)
