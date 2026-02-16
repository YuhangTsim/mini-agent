"""Unified CLI for mini-agent - defaults to roo-agent with open-agent option."""

from __future__ import annotations

import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()

# Configuration paths
DEFAULT_CONFIG_DIR = ".mini-agent"
DEFAULT_CONFIG_FILE = "config.toml"
GLOBAL_CONFIG_DIR = Path.home() / ".mini-agent"

# Provider presets
PROVIDER_PRESETS = {
    "openai": {
        "name": "openai",
        "model": "gpt-4o",
        "base_url": None,
        "env_var": "OPENAI_API_KEY",
        "description": "OpenAI API (GPT-4o, GPT-4o-mini, GPT-3.5)",
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
        "env_var": None,
        "description": "Ollama (local models)",
        "models": ["llama3.2", "qwen2.5", "mistral", "codellama"],
    },
    "openai_compatible": {
        "name": "custom",
        "model": "",
        "base_url": "",
        "env_var": None,
        "description": "Other OpenAI-compatible API (Together, vLLM, etc.)",
        "models": [],
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


def _save_config(
    provider_name: str,
    model: str,
    api_key: str,
    base_url: str | None,
    project_dir: Path | None = None,
) -> Path:
    """Save settings to a TOML config file."""
    if project_dir:
        config_dir = project_dir / DEFAULT_CONFIG_DIR
    else:
        config_dir = GLOBAL_CONFIG_DIR

    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / DEFAULT_CONFIG_FILE

    # Build TOML content
    lines = [
        "# Mini-Agent Configuration",
        "# Shared by both roo-agent (default) and open-agent (--open)",
        "",
        "# === Shared Provider (used by both) ===",
        "[provider]",
        f'name = "{provider_name}"',
        f'model = "{model}"',
    ]

    if base_url:
        lines.append(f'base_url = "{base_url}"')

    if api_key:
        lines.append(f'api_key = "{api_key}"')

    lines.extend([
        "max_tokens = 4096",
        "temperature = 0.0",
        "",
        "# === Roo-Agent Settings ===",
        'default_mode = "code"  # code, plan, ask, debug, orchestrator',
        "",
        "[tool_approval]",
        'read_file = "auto_approve"',
        'search_files = "auto_approve"',
        'list_files = "auto_approve"',
        'write_file = "always_ask"',
        'edit_file = "always_ask"',
        'execute_command = "always_ask"',
        '"*" = "ask_once"',
        "",
        "# === Open-Agent Settings ===",
        "[open_agent]",
        'default_agent = "orchestrator"',
        "max_delegation_depth = 3",
        "",
        "[open_agent.background]",
        "max_concurrent = 3",
        "",
        "[open_agent.agents.orchestrator]",
        'role = "orchestrator"',
        f'model = "{model}"',
        "temperature = 0.0",
        "",
        "[open_agent.agents.explorer]",
        'role = "explorer"',
        f'model = "{model}"',
    ])

    config_path.write_text("\n".join(lines))
    return config_path


def run_configuration_wizard(
    project_dir: Path | None = None, force: bool = False
) -> dict | None:
    """Run the interactive configuration wizard.

    Args:
        project_dir: If set, create project-local config. Otherwise, create global config.
        force: If True, run even if config already exists.

    Returns:
        Config dict if configured successfully, None if cancelled.
    """
    if not force and _config_exists(project_dir):
        config_path = _get_config_path(project_dir)
        console.print(f"[dim]Config already exists at {config_path}[/dim]")
        if not Confirm.ask("Overwrite existing configuration?", default=False):
            return None

    console.print(
        Panel(
            "[bold]Welcome to Mini-Agent![/bold]\n"
            "Let's configure your LLM provider.\n\n"
            "[dim]This config works for both:[/dim]\n"
            "  • [blue]roo-agent[/blue] (default) - Mode-based agent\n"
            "  • [green]open-agent[/green] (--open) - Multi-agent framework",
            border_style="blue",
        )
    )

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
        provider_name = Prompt.ask(
            "Provider name (e.g., 'together', 'vllm')", default="custom"
        )
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
            use_env = Confirm.ask(
                f"Use environment variable {env_var}?", default=True
            )
            if use_env:
                api_key = ""  # Will be resolved from env
            else:
                api_key = Prompt.ask("Enter API key", password=True)
        else:
            console.print(
                f"\n[yellow]Tip:[/yellow] Set {env_var} environment variable to avoid entering API key in config"
            )
            save_key = Confirm.ask(
                "Save API key in config file? (not recommended)", default=False
            )
            if save_key:
                api_key = Prompt.ask("Enter API key", password=True)
            else:
                console.print(
                    f"[dim]You'll need to set {env_var} before running mini-agent[/dim]"
                )
    elif selected_key == "ollama":
        console.print("\n[dim]Ollama runs locally, no API key required[/dim]")
        console.print("[dim]Make sure Ollama is running at http://localhost:11434[/dim]")

    # Choose config location
    if project_dir is None:
        use_global = Confirm.ask(
            "Save configuration globally (applies to all projects)?",
            default=True,
        )
        if not use_global:
            project_dir = Path(Prompt.ask("Enter project directory", default=os.getcwd()))

    # Save config
    config_path = _save_config(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        base_url=base_url,
        project_dir=project_dir,
    )

    console.print(f"\n[green]Configuration saved to:[/green] {config_path}")

    # Print summary
    api_key_display = (
        "saved in config"
        if api_key
        else ("from env var" if preset.get("env_var") else "not required")
    )
    console.print(
        Panel(
            f"[bold]Configuration Summary[/bold]\n"
            f"Provider: {provider_name}\n"
            f"Model: {model}\n"
            f"Base URL: {base_url or 'default'}\n"
            f"API Key: {api_key_display}\n\n"
            f"[dim]Run [bold]mini-agent[/bold] to start (roo-agent default)[/dim]\n"
            f"[dim]Run [bold]mini-agent --open[/bold] for open-agent[/dim]",
            border_style="green",
        )
    )

    return {
        "provider": provider_name,
        "model": model,
        "base_url": base_url,
        "config_path": str(config_path),
    }


def check_and_configure(config_path: str | Path | None = None) -> bool:
    """Check if configuration exists, run wizard if not.

    Returns:
        True if configuration is ready, False otherwise.
    """
    if config_path:
        return Path(config_path).exists()

    # Check project-local first, then global
    project_config = Path.cwd() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    global_config = GLOBAL_CONFIG_DIR / DEFAULT_CONFIG_FILE

    if project_config.exists() or global_config.exists():
        return True

    # No config found, run wizard
    console.print("[yellow]No configuration found. Running setup wizard...[/yellow]\n")
    result = run_configuration_wizard()
    return result is not None


@click.group(invoke_without_command=True)
@click.option(
    "--open",
    "use_open",
    is_flag=True,
    help="Use open-agent (multi-agent) instead of roo-agent (default)",
)
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--mode", default="code", help="Agent mode (roo-agent only)")
@click.option(
    "--configure", is_flag=True, help="Run configuration wizard"
)
@click.pass_context
def main(ctx, use_open, config, mode, configure):
    """Mini-Agent: AI agent framework (default: roo-agent, use --open for open-agent).

    \b
    Examples:
        mini-agent              # Start roo-agent (default)
        mini-agent --open       # Start open-agent (multi-agent)
        mini-agent --configure  # Run configuration wizard
    """
    # If a subcommand was invoked, let it handle everything
    if ctx.invoked_subcommand is not None:
        return

    # Handle --configure flag
    if configure:
        run_configuration_wizard(force=True)
        return

    # Check if we need to configure
    if not check_and_configure(config):
        console.print("[red]Configuration required. Run: mini-agent --configure[/red]")
        return

    if use_open:
        # Run open-agent
        console.print(
            Panel.fit(
                "[bold green]Open Agent[/] - Multi-agent event-driven framework",
                border_style="green",
            )
        )
        from open_agent.cli.app import run_repl
        from open_agent.config import Settings as OpenSettings
        import asyncio

        settings = OpenSettings.load(config)
        asyncio.run(run_repl(settings))
    else:
        # Default: roo-agent
        valid_modes = ("code", "plan", "ask", "debug", "orchestrator")
        if mode not in valid_modes:
            console.print(
                f"[red]Invalid mode '{mode}'. Valid modes: {', '.join(valid_modes)}[/red]"
            )
            return

        console.print(
            Panel.fit(
                "[bold blue]Roo Agent[/] - Mode-based agent framework (default)",
                border_style="blue",
            )
        )
        from roo_agent.cli.app import run_repl
        from roo_agent.cli.config_wizard import check_and_configure as roo_check
        import asyncio

        # Use roo-agent's check_and_configure for full setup
        settings = roo_check(config)
        settings.default_mode = mode
        asyncio.run(run_repl(settings))


@main.command()
@click.option("--global", "global_config", is_flag=True, help="Configure globally (default: project-local)")
@click.option("--force", is_flag=True, help="Force reconfiguration even if config exists")
def configure(global_config, force):
    """Run the configuration wizard to set up LLM provider."""
    project_dir = None if global_config else Path.cwd()
    run_configuration_wizard(project_dir=project_dir, force=force)


@main.command()
def version():
    """Show version information."""
    from mini_agent import __version__

    console.print(f"mini-agent version {__version__}")
    console.print("\n[dim]Included frameworks:[/dim]")
    console.print("  • roo-agent - Mode-based agent framework")
    console.print("  • open-agent - Multi-agent event-driven framework")


if __name__ == "__main__":
    main()
