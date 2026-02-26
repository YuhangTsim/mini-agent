"""Configuration management with TOML loading."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_DIR = ".mini-agent"
DEFAULT_CONFIG_FILE = "config.toml"
GLOBAL_CONFIG_DIR = Path.home() / ".mini-agent"


@dataclass
class ProviderConfig:
    name: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.0
    max_context: int | None = None
    max_output: int | None = None
    stream: bool = True  # Enable streaming by default

    @property
    def is_openai_compatible(self) -> bool:
        """Whether this provider uses the OpenAI-compatible API."""
        return self.name == "openai" or self.base_url is not None

    def resolve_api_key(self) -> str | None:
        """Resolve API key from config or environment. Returns None if not set."""
        if self.api_key:
            return self.api_key
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(self.name, f"{self.name.upper()}_API_KEY")
        return os.environ.get(env_var) or None


@dataclass
class ApprovalConfig:
    """Per-tool approval policies."""

    policies: dict[str, str] = field(default_factory=lambda: {
        "read_file": "auto_approve",
        "search_files": "auto_approve",
        "list_files": "auto_approve",
        "write_file": "always_ask",
        "edit_file": "always_ask",
        "execute_command": "always_ask",
        "attempt_completion": "auto_approve",
        "*": "ask_once",
    })

    def get_policy(self, tool_name: str) -> str:
        return self.policies.get(tool_name, self.policies.get("*", "ask_once"))


@dataclass
class ContextConfig:
    """Configuration for context management (truncation/condensation)."""

    enabled: bool = True
    strategy: str = "auto"  # "truncate" | "condense" | "auto"
    max_context_tokens: int | None = None  # Defaults to model max_context
    truncation_threshold: float = 0.85  # Start truncating at 85% of context
    condensation_threshold: float = 0.70  # Start condensing at 70%
    keep_recent_messages: int = 6  # Always keep N most recent messages
    summary_model: str = "gpt-4o-mini"  # Model for generating summaries


@dataclass
class Settings:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    approval: ApprovalConfig = field(default_factory=ApprovalConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    debug: bool = False
    default_mode: str = "code"
    working_directory: str = field(default_factory=lambda: os.getcwd())
    project_config_dir: str = DEFAULT_CONFIG_DIR
    data_dir: str = ""  # resolved lazily

    def __post_init__(self):
        if not self.data_dir:
            self.data_dir = os.path.join(self.working_directory, self.project_config_dir)

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "agent.db")

    @property
    def skills_dirs(self) -> list[Path]:
        """Skill search paths in priority order."""
        dirs = []
        # Project-level
        project_skills = Path(self.data_dir) / "skills"
        if project_skills.exists():
            dirs.append(project_skills)
        # Global
        global_skills = GLOBAL_CONFIG_DIR / "skills"
        if global_skills.exists():
            dirs.append(global_skills)
        return dirs

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Settings:
        """Load settings from TOML config file."""
        if config_path is None:
            # Try local config first, then fall back to global config
            local_config = Path(os.getcwd()) / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
            global_config = GLOBAL_CONFIG_DIR / DEFAULT_CONFIG_FILE
            
            if local_config.exists():
                config_path = local_config
            elif global_config.exists():
                config_path = global_config
            else:
                config_path = local_config  # Use local path as default

        config_path = Path(config_path)
        raw: dict[str, Any] = {}

        if config_path.exists():
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Settings:
        provider_data = data.get("provider", {})
        provider = ProviderConfig(
            name=provider_data.get("name", "openai"),
            model=provider_data.get("model", "gpt-4o"),
            api_key=provider_data.get("api_key", ""),
            base_url=provider_data.get("base_url"),
            max_tokens=provider_data.get("max_tokens", 4096),
            temperature=provider_data.get("temperature", 0.0),
            max_context=provider_data.get("max_context"),
            max_output=provider_data.get("max_output"),
        )

        approval_data = data.get("tool_approval", {})
        default_policies = ApprovalConfig().policies
        if approval_data:
            default_policies.update(approval_data)
        approval = ApprovalConfig(policies=default_policies)

        context_data = data.get("context", {})
        context = ContextConfig(
            enabled=context_data.get("enabled", True),
            strategy=context_data.get("strategy", "auto"),
            max_context_tokens=context_data.get("max_context_tokens"),
            truncation_threshold=context_data.get("truncation_threshold", 0.85),
            condensation_threshold=context_data.get("condensation_threshold", 0.70),
            keep_recent_messages=context_data.get("keep_recent_messages", 6),
            summary_model=context_data.get("summary_model", "gpt-4o-mini"),
        )

        return cls(
            provider=provider,
            approval=approval,
            context=context,
            debug=data.get("debug", False),
            default_mode=data.get("default_mode", "code"),
            working_directory=data.get("working_directory", os.getcwd()),
        )

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        os.makedirs(self.data_dir, exist_ok=True)
