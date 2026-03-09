"""Helpers for deterministic E2E test configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def provider_config_from_env() -> dict[str, Any]:
    """Build a provider config from exported test credentials."""
    if os.environ.get("OPENAI_API_KEY"):
        return {"name": "openai"}
    if os.environ.get("OPENROUTER_API_KEY"):
        return {
            "name": "openrouter",
            "base_url": OPENROUTER_BASE_URL,
        }
    raise RuntimeError("No API key available for E2E provider tests")


def make_roo_settings(tmp_path: Path):
    """Create Roo settings isolated to a temp working directory."""
    from roo_agent.config.settings import Settings

    return Settings._from_dict({
        "provider": provider_config_from_env(),
        "working_directory": str(tmp_path),
    })


def make_open_agent_settings(tmp_path: Path):
    """Create Open-Agent settings isolated to a temp working directory."""
    from open_agent.config import Settings

    return Settings._from_dict({
        "provider": provider_config_from_env(),
        "working_directory": str(tmp_path),
    })


def write_open_agent_config(config_path: Path, working_directory: Path) -> None:
    """Write a minimal Open-Agent config for CLI E2E tests."""
    provider = provider_config_from_env()
    lines = [
        "[provider]",
        f'name = "{provider["name"]}"',
    ]
    base_url = provider.get("base_url")
    if base_url:
        lines.append(f'base_url = "{base_url}"')
    lines.extend([
        "",
        f'working_directory = "{working_directory}"',
        "",
    ])
    config_path.write_text("\n".join(lines), encoding="utf-8")
