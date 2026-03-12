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

DEFAULT_CONFIG_DIR = ".mini-agent"
DEFAULT_CONFIG_FILE = "config.toml"
GLOBAL_CONFIG_DIR = Path.home() / ".mini-agent"

# Default tool approval policies for open-agent (compiled into low-priority PermissionRules)
DEFAULT_TOOL_APPROVAL: dict[str, str] = {
    "read": "auto_approve",
    "edit": "always_ask",
    "command": "always_ask",
    "report_result": "auto_approve",
    "*": "ask_once",
}


@dataclass
class ProviderConfig:
    name: str = "openai"
    api_key: str = ""
    base_url: str | None = None
    stream: bool = True
    model: str = "gpt-4.1"  # Enable streaming by default

    def resolve_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        env_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(self.name, f"{self.name.upper()}_API_KEY")
        return os.environ.get(env_var) or os.environ.get("OPENAI_API_KEY") or None


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
            "todo_write",
            "todo_read",
        ],
        "can_delegate_to": ["explorer", "librarian", "oracle", "designer", "fixer"],
    },
    "compaction": {
        "role": "compaction",
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "allowed_tools": [],  # No tools - read-only summarization
        "can_delegate_to": [],
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
class CompactionSettings:
    """Compaction configuration for context management."""

    enabled: bool = True  # Master switch for context management
    auto: bool = True  # Auto-compact when context is full
    auto_prune: bool = True
    prune_minimum: int = 20000
    prune_protect: int = 40000
    model: str = "gpt-4.1"


@dataclass
class Settings:
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    permissions: list[PermissionRule] = field(default_factory=list)
    debug: bool = False
    default_agent: str = "orchestrator"
    max_delegation_depth: int = 3
    background_max_concurrent: int = 3
    compaction: CompactionSettings = field(default_factory=CompactionSettings)
    working_directory: str = field(default_factory=lambda: os.getcwd())
    project_config_dir: str = DEFAULT_CONFIG_DIR
    data_dir: str = ""

    def __post_init__(self) -> None:
        if not self.data_dir:
            self.data_dir = os.path.join(self.working_directory, self.project_config_dir)
        # Load defaults for any agents not explicitly configured
        for role, defaults in DEFAULT_AGENTS.items():
            if role not in self.agents:
                # Use provider.model as default instead of hardcoded model
                agent_defaults = dict(defaults)
                agent_defaults["model"] = self.provider.model
                self.agents[role] = AgentConfig(**agent_defaults)

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "agent.db")

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
            # Search chain: project-local then global
            project_config = Path(os.getcwd()) / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
            global_config = GLOBAL_CONFIG_DIR / DEFAULT_CONFIG_FILE
            if project_config.exists():
                config_path = project_config
            elif global_config.exists():
                config_path = global_config

        raw: dict[str, Any] = {}

        if config_path is not None:
            config_path = Path(config_path)
            if config_path.exists():
                with open(config_path, "rb") as f:
                    raw = tomllib.load(f)

        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Settings":
        # Provider (shared top-level section)
        prov_data = data.get("providers", {}).get("openai", data.get("provider", {}))
        provider = ProviderConfig(
            name=prov_data.get("name", "openai"),
            api_key=prov_data.get("api_key", ""),
            base_url=prov_data.get("base_url"),
            stream=prov_data.get("stream", True),
            model=prov_data.get("model", "gpt-4.1"),
        )

        # Unwrap the open_agent namespace from unified config
        oa = data.get("open_agent", {})

        # Agents: prefer open_agent.agents, fall back to top-level agents
        agents: dict[str, AgentConfig] = {}
        agents_data = oa.get("agents", data.get("agents", {}))
        for role, agent_data in agents_data.items():
            agent_data = dict(agent_data)  # copy to avoid mutating config
            agent_data.setdefault("role", role)
            # Use provider.model as fallback if agent doesn't specify model
            agent_data.setdefault("model", provider.model)
            agents[role] = AgentConfig(**agent_data)

        # Permissions: explicit [[permissions]] rules (highest priority)
        permissions = [PermissionRule(**p) for p in data.get("permissions", [])]

        # Compile [open_agent.tool_approval] into low-priority PermissionRules
        tool_approval = oa.get("tool_approval", DEFAULT_TOOL_APPROVAL)
        for tool_pattern, policy_value in tool_approval.items():
            permissions.append(PermissionRule(agent="*", tool=tool_pattern, policy=policy_value))

        # General settings: prefer open_agent section, fall back to top-level general
        general = oa or data.get("general", {})
        background = oa.get("background", data.get("background", {}))

        # Compaction settings
        compaction_data = oa.get("compaction", {})
        compaction = CompactionSettings(
            enabled=compaction_data.get("enabled", True),
            auto=compaction_data.get("auto", True),
            auto_prune=compaction_data.get("auto_prune", True),
            prune_minimum=compaction_data.get("prune_minimum", 20000),
            prune_protect=compaction_data.get("prune_protect", 40000),
            model=compaction_data.get("model", provider.model),
        )

        return cls(
            provider=provider,
            agents=agents,
            permissions=permissions,
            debug=data.get("debug", False),
            default_agent=general.get("default_agent", "orchestrator"),
            max_delegation_depth=general.get("max_delegation_depth", 3),
            background_max_concurrent=background.get("max_concurrent", 3),
            compaction=compaction,
            working_directory=data.get("working_directory", os.getcwd()),
        )

    def ensure_dirs(self) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
