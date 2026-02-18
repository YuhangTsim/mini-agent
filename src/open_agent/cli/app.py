"""CLI REPL for Open-Agent with delegation display."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from open_agent.bus import Event, EventBus, EventPayload
from open_agent.config import Settings
from open_agent.core.app import OpenAgentApp
from open_agent.core.session import SessionCallbacks
from open_agent.persistence.models import TokenUsage
from open_agent.tools.base import ToolResult

console = Console()


class CLICallbacks:
    """CLI implementation of session callbacks with rich console rendering."""

    def __init__(self) -> None:
        self._live: Live | None = None
        self._streamed_text = ""

    async def on_text_delta(self, text: str) -> None:
        self._streamed_text += text
        if self._live is None:
            self._live = Live(console=console, refresh_per_second=8)
            self._live.start()
        self._live.update(Markdown(self._streamed_text))

    async def on_tool_call_start(self, call_id: str, name: str, args: str) -> None:
        self._flush_live()
        console.print(f"  [dim]▶ {name}[/dim]", end="")

    async def on_tool_call_end(self, call_id: str, name: str, result: ToolResult) -> None:
        if result.is_error:
            console.print(f" [red]✗ {result.error[:100]}[/red]")
        elif name == "report_result":
            # For report_result, extract and display the actual result content
            # The result.output is "Result reported: {actual_result}"
            prefix = "Result reported: "
            if result.output.startswith(prefix):
                actual_result = result.output[len(prefix):]
                console.print(" [green]✓ Result reported[/green]")
                console.print()
                console.print(Markdown(actual_result))
            else:
                console.print(f" [green]✓[/green] {result.output}")
        else:
            output_preview = result.output[:80].replace("\n", " ")
            console.print(f" [green]✓[/green] [dim]{output_preview}[/dim]")

    async def on_tool_approval_request(self, name: str, call_id: str, params: dict) -> str:
        self._flush_live()
        console.print()
        console.print(
            Panel(
                f"[bold]{name}[/bold]\n{_format_params(params)}",
                title="Tool Approval",
                border_style="yellow",
            )
        )
        while True:
            response = console.input("[yellow]Allow? (y/n/always): [/yellow]").strip().lower()
            if response in ("y", "n", "always"):
                return response
            console.print("[dim]Please enter y, n, or always[/dim]")

    async def request_user_input(self, question: str, suggestions: list[str] | None) -> str:
        self._flush_live()
        console.print()
        console.print(f"[bold cyan]? {question}[/bold cyan]")
        if suggestions:
            for i, s in enumerate(suggestions, 1):
                console.print(f"  [dim]{i}.[/dim] {s}")
            console.print(f"  [dim]{len(suggestions) + 1}.[/dim] (custom)")

        response = console.input("[cyan]> [/cyan]").strip()

        # Check if they picked a number
        if suggestions and response.isdigit():
            idx = int(response) - 1
            if 0 <= idx < len(suggestions):
                return suggestions[idx]

        return response

    async def on_message_end(self, usage: TokenUsage) -> None:
        self._flush_live()
        if usage.input_tokens or usage.output_tokens:
            console.print(
                f"\n[dim]tokens: {usage.input_tokens} in / {usage.output_tokens} out[/dim]"
            )

    def _flush_live(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None
        if self._streamed_text:
            self._streamed_text = ""


class DelegationDisplay:
    """Subscribes to bus events to show delegation activity in the CLI."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        self.bus.subscribe(Event.DELEGATION_START, self._on_delegation_start)
        self.bus.subscribe(Event.DELEGATION_END, self._on_delegation_end)
        self.bus.subscribe(Event.BACKGROUND_TASK_QUEUED, self._on_bg_queued)
        self.bus.subscribe(Event.BACKGROUND_TASK_COMPLETE, self._on_bg_complete)
        self.bus.subscribe(Event.BACKGROUND_TASK_FAILED, self._on_bg_failed)
        self.bus.subscribe(Event.AGENT_START, self._on_agent_start)

    async def _on_delegation_start(self, payload: EventPayload) -> None:
        target = payload.data.get("target_role", "?")
        desc = payload.data.get("description", "")[:80]
        console.print(f"\n[bold blue]→ Delegating to {target}:[/bold blue] {desc}")

    async def _on_delegation_end(self, payload: EventPayload) -> None:
        target = payload.data.get("target_role", "?")
        console.print(f"[bold blue]← {target} done[/bold blue]")

    async def _on_bg_queued(self, payload: EventPayload) -> None:
        task_id = payload.data.get("task_id", "?")[:8]
        desc = payload.data.get("description", "")[:60]
        console.print(f"[dim]⟳ Background task {task_id}...: {desc}[/dim]")

    async def _on_bg_complete(self, payload: EventPayload) -> None:
        task_id = payload.data.get("task_id", "?")[:8]
        console.print(f"[green]✓ Background task {task_id}... complete[/green]")

    async def _on_bg_failed(self, payload: EventPayload) -> None:
        task_id = payload.data.get("task_id", "?")[:8]
        error = payload.data.get("error", "unknown")[:60]
        console.print(f"[red]✗ Background task {task_id}... failed: {error}[/red]")

    async def _on_agent_start(self, payload: EventPayload) -> None:
        role = payload.agent_role
        if role != "orchestrator":
            console.print(f"\n[dim]── {role} ──[/dim]")


def _format_params(params: dict) -> str:
    """Format tool params for display."""
    lines = []
    for k, v in params.items():
        val = str(v)
        if len(val) > 100:
            val = val[:100] + "..."
        lines.append(f"  {k}: {val}")
    return "\n".join(lines)


async def run_repl(settings: Settings | None = None) -> None:
    """Run the interactive REPL."""
    app = OpenAgentApp(settings)
    await app.initialize()

    cli_callbacks = CLICallbacks()
    app.set_callbacks(
        SessionCallbacks(
            on_text_delta=cli_callbacks.on_text_delta,
            on_tool_call_start=cli_callbacks.on_tool_call_start,
            on_tool_call_end=cli_callbacks.on_tool_call_end,
            on_tool_approval_request=cli_callbacks.on_tool_approval_request,
            request_user_input=cli_callbacks.request_user_input,
            on_message_end=cli_callbacks.on_message_end,
        )
    )

    # Set up delegation display (subscribes to bus events via __init__)
    DelegationDisplay(app.bus)

    provider = app.settings.provider
    tool_count = len(app.tool_registry.all_tools())
    default_agent = app.agent_registry.get_required(app.settings.default_agent)
    console.print(
        Panel(
            "[bold]Open-Agent[/bold] — Multi-agent AI framework\n"
            f"[dim]Provider: {provider.name} | "
            f"Default model: {default_agent.config.model}[/dim]\n"
            f"[dim]Default agent: {app.settings.default_agent} | "
            f"Agents: {', '.join(app.agent_registry.roles())} | "
            f"Tools: {tool_count}[/dim]",
            border_style="blue",
        )
    )
    console.print("[dim]Type your message. Ctrl+C or 'exit' to quit.[/dim]\n")

    # Set up prompt_toolkit with history
    history_dir = Path(app.settings.data_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "open_agent_repl_history"
    session = PromptSession(history=FileHistory(str(history_file)))

    try:
        while True:
            try:
                user_input = (await session.prompt_async("▶ ")).strip()
            except EOFError:
                break

            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                break

            # Handle commands
            if user_input.startswith("/"):
                await _handle_command(user_input, app)
                continue

            try:
                await app.process_message(user_input)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

            console.print()

    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")
    finally:
        await app.shutdown()


async def _handle_command(cmd: str, app: OpenAgentApp) -> None:
    """Handle slash commands."""
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()

    if command == "/agents":
        console.print("\n[bold]Registered Agents:[/bold]")
        for agent in app.agent_registry.all_agents():
            delegates = ", ".join(agent.config.can_delegate_to) or "(leaf)"
            console.print(
                f"  [cyan]{agent.role:12}[/cyan] | "
                f"model={agent.config.model:15} | "
                f"delegates_to={delegates}"
            )
        console.print()

    elif command == "/tools":
        console.print("\n[bold]Registered Tools:[/bold]")
        for tool in app.tool_registry.all_tools():
            console.print(f"  [cyan]{tool.name:25}[/cyan] {tool.category}")
        console.print()

    elif command == "/history":
        sessions = await app.store.list_sessions(limit=10)
        if not sessions:
            console.print("\n[dim]No sessions found.[/dim]\n")
        else:
            console.print("\n[bold]Recent Sessions:[/bold]")
            for s in sessions:
                status_color = "green" if s.status.value == "completed" else "yellow"
                title = s.title[:60] if s.title else "(untitled)"
                console.print(
                    f"  [{status_color}]{s.status.value:10}[/{status_color}] "
                    f"{s.id[:8]}... | {title} | "
                    f"{s.token_usage.input_tokens}in/{s.token_usage.output_tokens}out"
                )
            console.print()

    elif command == "/model":
        provider = app.settings.provider
        console.print("\n[bold]Provider & Model Info:[/bold]")
        console.print(f"  Provider: {provider.name}")
        if provider.base_url:
            console.print(f"  Base URL: {provider.base_url}")
        console.print(f"  API Key:  {'set' if provider.resolve_api_key() else 'not set'}")
        console.print("\n[bold]Per-Agent Models:[/bold]")
        for agent in app.agent_registry.all_agents():
            console.print(
                f"  [cyan]{agent.role:12}[/cyan] | "
                f"model={agent.config.model} | "
                f"temp={agent.config.temperature}"
            )
        console.print()

    elif command == "/session":
        if app._session is None:
            console.print("\n[dim]No active session yet.[/dim]\n")
        else:
            s = app._session
            console.print("\n[bold]Current Session:[/bold]")
            console.print(f"  ID:      {s.id}")
            console.print(f"  Status:  {s.status.value}")
            console.print(f"  Title:   {s.title or '(untitled)'}")
            console.print(f"  Dir:     {s.working_directory}")
            console.print(
                f"  Tokens:  {s.token_usage.input_tokens} in / "
                f"{s.token_usage.output_tokens} out"
            )
            console.print(f"  Created: {s.created_at.isoformat()}")
            console.print()

    elif command == "/help":
        console.print("\n[bold]Commands:[/bold]")
        console.print("  /agents   — List registered agents")
        console.print("  /tools    — List registered tools")
        console.print("  /history  — List recent sessions")
        console.print("  /model    — Show provider and per-agent model info")
        console.print("  /session  — Show current session details")
        console.print("  /help     — Show this help")
        console.print("  exit      — Quit")
        console.print()

    else:
        console.print(f"[dim]Unknown command: {command}. Try /help[/dim]")


@click.group(invoke_without_command=True)
@click.option("-c", "--config", "config_path", default=None, help="Path to config file")
@click.pass_context
def cli(ctx: click.Context, config_path: str | None) -> None:
    """Open-Agent: Multi-agent AI framework."""
    if ctx.invoked_subcommand is None:
        settings = Settings.load(config_path) if config_path else None
        asyncio.run(run_repl(settings))


@cli.command()
@click.option("-c", "--config", "config_path", default=None, help="Path to config file")
def chat(config_path: str | None) -> None:
    """Start interactive chat (default)."""
    settings = Settings.load(config_path) if config_path else None
    asyncio.run(run_repl(settings))


def main() -> None:
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
