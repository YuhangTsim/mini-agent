"""Helpers for deterministic and live E2E test configuration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_REPORT_PATH = Path(".mini-agent") / "tool-calling-certification.jsonl"


@dataclass(frozen=True)
class LiveModelTarget:
    """A single live provider/model target used for certification."""

    key: str
    provider_name: str
    model: str
    api_key_env: str
    base_url: str | None = None
    route: str = "direct"

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def provider_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "name": self.provider_name,
            "model": self.model,
        }
        if self.base_url:
            config["base_url"] = self.base_url
        return config


def _live_target_specs() -> list[LiveModelTarget]:
    return [
        LiveModelTarget(
            key="openai_economy",
            provider_name="openai",
            model=os.environ.get("E2E_OPENAI_MODEL", "gpt-4o-mini"),
            api_key_env="OPENAI_API_KEY",
            route="direct",
        ),
        LiveModelTarget(
            key="claude_openrouter",
            provider_name="openrouter",
            model=os.environ.get(
                "E2E_OPENROUTER_CLAUDE_MODEL",
                "anthropic/claude-sonnet-4.5",
            ),
            api_key_env="OPENROUTER_API_KEY",
            base_url=OPENROUTER_BASE_URL,
            route="openrouter",
        ),
        LiveModelTarget(
            key="gemini_openrouter",
            provider_name="openrouter",
            model=os.environ.get(
                "E2E_OPENROUTER_GEMINI_MODEL",
                "google/gemini-2.5-flash-lite",
            ),
            api_key_env="OPENROUTER_API_KEY",
            base_url=OPENROUTER_BASE_URL,
            route="openrouter",
        ),
        LiveModelTarget(
            key="minimax_openrouter",
            provider_name="openrouter",
            model=os.environ.get(
                "E2E_OPENROUTER_MINIMAX_MODEL",
                "minimax/minimax-m2.5",
            ),
            api_key_env="OPENROUTER_API_KEY",
            base_url=OPENROUTER_BASE_URL,
            route="openrouter",
        ),
        LiveModelTarget(
            key="kimi_openrouter",
            provider_name="openrouter",
            model=os.environ.get(
                "E2E_OPENROUTER_KIMI_MODEL",
                "moonshotai/kimi-k2.5",
            ),
            api_key_env="OPENROUTER_API_KEY",
            base_url=OPENROUTER_BASE_URL,
            route="openrouter",
        ),
    ]


def available_live_model_targets() -> list[LiveModelTarget]:
    """Return the configured live certification targets with available credentials."""
    targets = [target for target in _live_target_specs() if target.is_available]
    requested = os.environ.get("E2E_TARGETS", "").strip()
    if not requested:
        return targets

    requested_keys = {part.strip() for part in requested.split(",") if part.strip()}
    return [target for target in targets if target.key in requested_keys]


def provider_config_from_env() -> dict[str, Any]:
    """Build a provider config from exported test credentials."""
    if os.environ.get("OPENAI_API_KEY"):
        return {"name": "openai", "model": os.environ.get("E2E_OPENAI_MODEL", "gpt-4o-mini")}
    if os.environ.get("OPENROUTER_API_KEY"):
        return {
            "name": "openrouter",
            "model": os.environ.get(
                "E2E_OPENROUTER_DEFAULT_MODEL",
                "anthropic/claude-sonnet-4.5",
            ),
            "base_url": OPENROUTER_BASE_URL,
        }
    raise RuntimeError("No API key available for E2E provider tests")


def make_roo_settings(tmp_path: Path, target: LiveModelTarget | None = None):
    """Create Roo settings isolated to a temp working directory."""
    from roo_agent.config.settings import Settings

    provider = target.provider_config() if target is not None else provider_config_from_env()
    return Settings._from_dict({
        "provider": provider,
        "working_directory": str(tmp_path),
    })


def make_open_agent_settings(tmp_path: Path, target: LiveModelTarget | None = None):
    """Create Open-Agent settings isolated to a temp working directory."""
    from open_agent.config import Settings

    provider = target.provider_config() if target is not None else provider_config_from_env()
    settings = Settings._from_dict({
        "provider": {
            "name": provider["name"],
            "base_url": provider.get("base_url"),
        },
        "working_directory": str(tmp_path),
    })

    if target is not None:
        for agent in settings.agents.values():
            agent.model = target.model
        settings.compaction.model = target.model

    return settings


def write_open_agent_config(
    config_path: Path,
    working_directory: Path,
    target: LiveModelTarget | None = None,
) -> None:
    """Write a minimal Open-Agent config for CLI E2E tests."""
    provider = target.provider_config() if target is not None else provider_config_from_env()
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


def append_live_result(
    *,
    target: LiveModelTarget,
    scenario: str,
    status: str,
    failure_bucket: str | None = None,
    failure_reason: str | None = None,
) -> Path:
    """Append a machine-readable certification result."""
    report_path = Path(os.environ.get("E2E_TOOL_CALLING_REPORT_PATH", DEFAULT_REPORT_PATH))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": asdict(target),
        "scenario": scenario,
        "status": status,
        "failure_bucket": failure_bucket,
        "failure_reason": failure_reason,
    }
    with report_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return report_path
