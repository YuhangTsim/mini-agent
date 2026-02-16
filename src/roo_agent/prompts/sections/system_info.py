"""System information section."""

from __future__ import annotations

import os
import platform
from datetime import datetime, timezone
from typing import Any


def build_system_info_section(context: dict[str, Any]) -> str:
    """Build system information section."""
    working_dir = context.get("working_directory", "")
    agent_config = context["agent_config"]

    lines = [
        "====",
        "",
        "SYSTEM INFORMATION",
        "",
        f"Operating System: {platform.system()} {platform.release()}",
        f"Default Shell: {os.environ.get('SHELL', '/bin/sh')}",
        f"Home Directory: {os.path.expanduser('~')}",
        f"Current Workspace Directory: {working_dir}",
        f"Current Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"Agent Role: {agent_config.role}",
        f"Agent Name: {agent_config.name}",
    ]

    return "\n".join(lines)
