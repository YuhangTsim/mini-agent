"""Configuration management with TOML loading and multi-agent support."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from open_agent.config.agents import AgentConfig, PermissionRule

if sys.version_info >= (3, 12):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

# Use unified config with roo-agent
DEFAULT_CONFIG_DIR = ".mini-agent"
DEFAULT_CONFIG_FILE = "config.toml"
GLOBAL_CONFIG_DIR = Path.home() / ".mini-agent"


@dataclass
class ProviderConfig:
    name: str = "openai"
    api_key: str = ""
    base_url: str | None = None

    def resolve_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(self.name, f"{self.name.upper()}_API_KEY")
        return os.environ.get(env_var) or None


# Default agent configs matching the actual agent classes
DEFAULT_AGENTS: dict[str, dict[str, Any]] = {
    "orchestrator": {
        "role": "orchestrator",
        "model": "gpt-4o",
        "temperature": 0.0,
        "allowed_tools": [
            "delegate_task",
            "delegate_background",
            "check_background_task",
            "report_result",
        ],
        "can_delegate_to": ["explorer", "librarian", "oracle", "designer", "fixer"],
    },
    "explorer": {
        "role": "explorer",
        "model": "gpt-4o-mini",
        "allowed_tools": ["read_file", "search_files", "list_files", "report_result"],
    },
    "librarian": {
        "role": "librarian",
        "model": "gpt-4o",
        "allowed_tools": ["read_file", "search_files", "list_files", "report_result"],
    },
    "oracle": {
        "role": "oracle",
        "model": "gpt-4o",
        "temperature": 0.2,
        "allowed_tools": [
            "read_file",
            "search_files",
            "list_files",
            "delegate_task",
            "report_result",
        ],
        "can_delegate_to": ["explorer"],
    },
    "designer": {
        "role": "designer",
        "model": "gpt-4o",
        "allowed_tools": [
            "read_file",
            "write_file",
            "edit_file",
            "search_files",
            "list_files",
            "execute_command",
            "report_result",
        ],
    },
    "fixer": {
        "role": "fixer",
        "model": "gpt-4o",
        "allowed_tools": [
            "read_file",
            "write_file",
            "edit_file",
            "search_files",
            "list_files",
            "execute_command",
            "report_result",
        ],
    },
}


@dataclass
class Settings:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    permissions: list[PermissionRule] = field(default_factory=list)
    default_agent: str = "orchestrator"
    max_delegation_depth: int = 3
    background_max_concurrent: int = 3
    working_directory: str = field(default_factory=lambda: os.getcwd())
    project_config_dir: str = DEFAULT_CONFIG_DIR
    data_dir: str = ""

    def __post_init__(self) -> None:
        if not self.data_dir:
            self.data_dir = os.path.join(self.working_directory, self.project_config_dir)
        # Load defaults for any agents not explicitly configured
        for role, defaults in DEFAULT_AGENTS.items():
            if role not in self.agents:
                self.agents[role] = AgentConfig(**defaults)

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "sessions.db")

    @property
    def skills_dirs(self) -> list[Path]:
        dirs: list[Path] = []
        project_skills = Path(self.data_dir) / "skills"
        if project_skills.exists():
            dirs.append(project_skills)
        global_skills = GLOBAL_CONFIG_DIR / "skills"
        if global_skills.exists():
            dirs.append(global_skills)
        return dirs

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Settings":
        if config_path is None:
            config_path = Path(os.getcwd()) / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE

        config_path = Path(config_path)
        raw: dict[str, Any] = {}

        if config_path.exists():
            with open(config_path, "rb") as f:
                raw = tomllib.load(f)

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Settings":
        # Provider - try [providers.openai] first (legacy), then [provider] (unified)
        prov_data = data.get("providers", {}).get("openai", data.get("provider", {}))
        provider = ProviderConfig(
            name=prov_data.get("name", "openai"),
            api_key=prov_data.get("api_key", ""),
            base_url=prov_data.get("base_url"),
        )

        # Agents - check [open_agent.agents] first (unified), then [agents] (legacy)
        agents: dict[str, AgentConfig] = {}
        open_agent_section = data.get("open_agent", {})
        agents_data = open_agent_section.get("agents", data.get("agents", {}))
        for role, agent_data in agents_data.items():
            agent_data.setdefault("role", role)
            agents[role] = AgentConfig(**agent_data)

        # Permissions
        permissions = [PermissionRule(**p) for p in data.get("permissions", [])]

        # General settings - check [open_agent] first, then [general] (legacy)
        general = open_agent_section if open_agent_section else data.get("general", {})
        background = open_agent_section.get("background", data.get("background", {}))

        return cls(
            provider=provider,
            agents=agents,
            permissions=permissions,
            default_agent=general.get("default_agent", "orchestrator"),
            max_delegation_depth=general.get("max_delegation_depth", 3),
            background_max_concurrent=background.get("max_concurrent", 3),
            working_directory=data.get("working_directory", os.getcwd()),
        )

    def ensure_dirs(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
