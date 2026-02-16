"""Unified CLI for mini-agent - defaults to roo-agent with open-agent option."""

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command()
@click.option(
    "--open", "use_open",
    is_flag=True,
    help="Use open-agent (multi-agent) instead of roo-agent (default)"
)
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--mode", default="coder", help="Agent mode (roo-agent only)")
@click.pass_context
def main(ctx, use_open, config, mode):
    """Mini-Agent: AI agent framework (default: roo-agent, use --open for open-agent)."""
    if use_open:
        # Run open-agent
        console.print(Panel.fit(
            "[bold green]Open Agent[/] - Multi-agent event-driven framework",
            border_style="green"
        ))
        from open_agent.cli.app import run_repl
        from open_agent.config import Settings as OpenSettings
        import asyncio
        
        settings = OpenSettings.load(config)
        asyncio.run(run_repl(settings))
    else:
        # Default: roo-agent
        console.print(Panel.fit(
            "[bold blue]Roo Agent[/] - Mode-based agent framework (default)",
            border_style="blue"
        ))
        from roo_agent.cli.app import run_repl
        from roo_agent.config.settings import Settings as RooSettings
        import asyncio
        
        settings = RooSettings.load(config)
        settings.default_mode = mode
        asyncio.run(run_repl(settings))


@click.group()
def cli():
    """Mini-Agent CLI commands."""
    pass


@cli.command(name="version")
def version_cmd():
    """Show version information."""
    from mini_agent import __version__
    console.print(f"mini-agent version {__version__}")


if __name__ == "__main__":
    main()
