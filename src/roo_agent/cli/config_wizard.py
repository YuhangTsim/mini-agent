"""Interactive configuration wizard for first-run setup."""

from __future__ import annotations

import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from ..config.settings import Settings, ProviderConfig, DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_FILE, GLOBAL_CONFIG_DIR

console = Console()

# Pre-configured provider presets
PROVIDER_PRESETS = {
    "openai": {
        "name": "openai",
        "model": "gpt-4o",
        "base_url": None,
        "env_var": "OPENAI_API_KEY",
        "description": "OpenAI API (GPT-4, GPT-3.5)",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "openrouter": {
        "name": "openrouter",
        "model": "anthropic/claude-sonnet-4-20250514",
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY",
        "description": "OpenRouter (unified API for many models)",
        "models": [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4",
            "openai/gpt-4o",
            "google/gemini-2.5-flash-preview",
        ],
    },
    "ollama": {
        "name": "ollama",
        "model": "llama3.2",
        "base_url": "http://localhost:11434/v1",
        "env_var": None,  # Local, no API key needed
        "description": "Ollama (local models)",
        "models": ["llama3.2", "qwen2.5", "mistral", "codellama"],
    },
    "openai_compatible": {
        "name": "custom",
        "model": "",
        "base_url": "",
        "env_var": None,  # User will specify
        "description": "Other OpenAI-compatible API (Together, vLLM, etc.)",
        "models": [],  # User specifies
    },
}


def _get_config_path(project_dir: Path | None = None) -> Path:
    """Get the path to the config file."""
    if project_dir:
        return project_dir / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    return GLOBAL_CONFIG_DIR / DEFAULT_CONFIG_FILE


def _config_exists(project_dir: Path | None = None) -> bool:
    """Check if a config file already exists."""
    config_path = _get_config_path(project_dir)
    return config_path.exists()


def _save_config(settings: Settings, project_dir: Path | None = None) -> Path:
    """Save settings to a TOML config file."""
    if project_dir:
        config_dir = project_dir / DEFAULT_CONFIG_DIR
    else:
        config_dir = GLOBAL_CONFIG_DIR
    
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / DEFAULT_CONFIG_FILE
    
    # Build TOML content
    lines = [
        "# Roo Agent Configuration",
        "",
        f'default_mode = "{settings.default_mode}"',
        "",
        "[provider]",
        f'name = "{settings.provider.name}"',
        f'model = "{settings.provider.model}"',
    ]
    
    if settings.provider.base_url:
        lines.append(f'base_url = "{settings.provider.base_url}"')
    
    if settings.provider.api_key:
        lines.append(f'api_key = "{settings.provider.api_key}"')
    
    if settings.provider.max_context:
        lines.append(f"max_context = {settings.provider.max_context}")
    
    if settings.provider.max_output:
        lines.append(f"max_output = {settings.provider.max_output}")
    
    lines.extend([
        f"max_tokens = {settings.provider.max_tokens}",
        f"temperature = {settings.provider.temperature}",
        "",
        "[tool_approval]",
        'read_file = "auto_approve"',
        'search_files = "auto_approve"',
        'list_files = "auto_approve"',
        'write_file = "always_ask"',
        'edit_file = "always_ask"',
        'execute_command = "always_ask"',
        '"*" = "ask_once"',
    ])
    
    config_path.write_text("\n".join(lines))
    return config_path


def run_configuration_wizard(project_dir: Path | None = None, force: bool = False) -> Settings | None:
    """Run the interactive configuration wizard.
    
    Args:
        project_dir: If set, create project-local config. Otherwise, create global config.
        force: If True, run even if config already exists.
    
    Returns:
        Settings object if configured successfully, None if cancelled.
    """
    if not force and _config_exists(project_dir):
        config_path = _get_config_path(project_dir)
        console.print(f"[dim]Config already exists at {config_path}[/dim]")
        if not Confirm.ask("Overwrite existing configuration?", default=False):
            return Settings.load(config_path)
    
    console.print(Panel(
        "[bold]Welcome to Roo Agent![/bold]\n"
        "Let's configure your LLM provider.",
        border_style="blue",
    ))
    
    # Show provider options
    console.print("\n[bold]Select a provider:[/bold]")
    table = Table(show_header=False)
    table.add_column("#")
    table.add_column("Provider")
    table.add_column("Description")
    
    preset_keys = list(PROVIDER_PRESETS.keys())
    for i, key in enumerate(preset_keys, 1):
        preset = PROVIDER_PRESETS[key]
        table.add_row(str(i), key.replace("_", "-").title(), preset["description"])
    
    console.print(table)
    
    # Get selection
    choice = Prompt.ask(
        "Enter number",
        choices=[str(i) for i in range(1, len(preset_keys) + 1)],
        default="1",
    )
    selected_key = preset_keys[int(choice) - 1]
    preset = PROVIDER_PRESETS[selected_key]
    
    # Configure based on preset
    provider_name = preset["name"]
    base_url = preset["base_url"]
    model = preset["model"]
    api_key = ""
    
    # Handle custom/OpenAI-compatible
    if selected_key == "openai_compatible":
        console.print("\n[bold]OpenAI-Compatible Provider Configuration[/bold]")
        provider_name = Prompt.ask("Provider name (e.g., 'together', 'vllm')", default="custom")
        base_url = Prompt.ask("Base URL (e.g., https://api.together.xyz/v1)")
        model = Prompt.ask("Model name (e.g., meta-llama/Llama-3-70b-chat-hf)")
    else:
        console.print(f"\n[bold]Configuring {preset['description']}[/bold]")
    
    # Show model options for presets with known models
    if preset["models"] and selected_key != "openai_compatible":
        console.print("\nSelect a model:")
        for i, m in enumerate(preset["models"], 1):
            marker = " *" if m == preset["model"] else ""
            console.print(f"  {i}. {m}{marker}")
        console.print(f"  {len(preset['models']) + 1}. Other (custom)")
        
        model_choice = Prompt.ask(
            "Enter number",
            choices=[str(i) for i in range(1, len(preset["models"]) + 2)],
            default="1",
        )
        if int(model_choice) <= len(preset["models"]):
            model = preset["models"][int(model_choice) - 1]
        else:
            model = Prompt.ask("Enter model name")
    
    # Get API key
    if preset["env_var"]:
        env_var = preset["env_var"]
        existing_key = os.environ.get(env_var)
        
        if existing_key:
            console.print(f"\n[green]Found {env_var} in environment[/green]")
            use_env = Confirm.ask(f"Use environment variable {env_var}?", default=True)
            if use_env:
                api_key = ""  # Will be resolved from env
            else:
                api_key = Prompt.ask(f"Enter API key", password=True)
        else:
            console.print(f"\n[yellow]Set {env_var} environment variable to avoid entering API key in config[/yellow]")
            save_key = Confirm.ask("Save API key in config file? (not recommended)", default=False)
            if save_key:
                api_key = Prompt.ask(f"Enter API key", password=True)
            else:
                console.print(f"[dim]You'll need to set {env_var} before running roo-agent[/dim]")
    elif selected_key == "ollama":
        console.print("\n[dim]Ollama runs locally, no API key required[/dim]")
        # Check if Ollama is running
        console.print("[dim]Make sure Ollama is running at http://localhost:11434[/dim]")
    
    # Choose config location
    if project_dir is None:
        use_global = Confirm.ask(
            "Save configuration globally (applies to all projects)?",
            default=True,
        )
        if not use_global:
            project_dir = Path(Prompt.ask("Enter project directory", default=os.getcwd()))
    
    # Create settings
    provider_config = ProviderConfig(
        name=provider_name,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
    
    settings = Settings(
        provider=provider_config,
        working_directory=str(project_dir or os.getcwd()),
    )
    
    # Save config
    config_path = _save_config(settings, project_dir)
    console.print(f"\n[green]Configuration saved to:[/green] {config_path}")
    
    # Print summary
    console.print(Panel(
        f"[bold]Configuration Summary[/bold]\n"
        f"Provider: {provider_name}\n"
        f"Model: {model}\n"
        f"Base URL: {base_url or 'default'}\n"
        f"API Key: {'saved in config' if api_key else ('from env var' if preset.get('env_var') else 'not required')}",
        border_style="green",
    ))
    
    return settings


def check_and_configure(config_path: str | Path | None = None, force: bool = False) -> Settings:
    """Check if configuration exists, run wizard if not.
    
    Args:
        config_path: Optional explicit config path
        force: Force reconfiguration even if config exists
    
    Returns:
        Settings object
    """
    # Try to load existing config
    settings = Settings.load(config_path)
    
    # Check if provider is properly configured
    api_key = settings.provider.resolve_api_key()
    
    # If no API key and not a local provider like Ollama, run wizard
    if force or (not api_key and not settings.provider.base_url):
        console.print("[yellow]No API key configured. Running setup wizard...[/yellow]\n")
        new_settings = run_configuration_wizard(force=force)
        if new_settings:
            return new_settings
    
    return settings
