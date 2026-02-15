"""System information section."""

from __future__ import annotations

import os
import platform
from datetime import datetime
from typing import Any


def build_system_info_section(context: dict[str, Any]) -> str:
    """Build system information section."""
    task = context.get("task")
    working_dir = context.get("working_directory", "")
    mode = context.get("mode")

    lines = [
        "====",
        "",
        "SYSTEM INFORMATION",
        "",
        f"Operating System: {platform.system()} {platform.release()}",
        f"Default Shell: {os.environ.get('SHELL', '/bin/sh')}",
        f"Home Directory: {os.path.expanduser('~')}",
        f"Current Workspace Directory: {working_dir}",
        f"Current Date: {datetime.utcnow().strftime('%Y-%m-%d')}",
    ]

    if mode:
        lines.append(f"Current Mode: {mode.name} ({mode.slug})")

    if task and task.todo_list:
        lines.append("")
        lines.append("Current Todo List:")
        for item in task.todo_list:
            check = "[x]" if item.done else "[ ]"
            lines.append(f"- {check} {item.text}")

    return "\n".join(lines)
