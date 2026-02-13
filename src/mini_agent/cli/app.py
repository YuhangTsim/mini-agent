"""CLI entry point and interactive REPL with full agent loop."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

import click
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from ..config.settings import Settings
from ..core.agent import Agent, AgentCallbacks
from ..core.mode import ModeConfig, get_mode, list_modes
from ..persistence.export import export_task
from ..persistence.models import Task, TaskStatus, TokenUsage, new_id
from ..persistence.store import Store
from ..providers.registry import create_provider
from ..tools.base import ToolRegistry, ToolResult
from ..tools.native import get_all_native_tools
from ..tools.native.skill_tool import SkillTool
from ..tools.agent import get_all_agent_tools
from ..prompts.builder import PromptBuilder
from ..skills.manager import SkillsManager

console = Console()


class CLICallbacks:
    """CLI implementation of agent callbacks."""

    def __init__(self, prompt_session: PromptSession):
        self._session = prompt_session
        self._live: Live | None = None
        self._streaming_text = ""

    def start_live(self) -> Live:
        self._streaming_text = ""
        self._live = Live(console=console, refresh_per_second=15)
        self._live.start()
        return self._live

    def stop_live(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    async def on_text_delta(self, text: str) -> None:
        self._streaming_text += text
        if self._live:
            self._live.update(Markdown(self._streaming_text))

    async def on_tool_call_start(self, call_id: str, name: str, args: str) -> None:
        self.stop_live()
        console.print(f"\n[yellow]Tool:[/yellow] {name}", end="")

    async def on_tool_call_end(self, call_id: str, name: str, result: ToolResult) -> None:
        if result.is_error:
            console.print(f"  [red]Error:[/red] {result.error}")
        else:
            output = result.output
            if len(output) > 500:
                output = output[:500] + "..."
            console.print(f"  [green]OK[/green]")
            if output.strip():
                console.print(f"[dim]{output}[/dim]")
        self.start_live()

    async def on_tool_approval_request(
        self, name: str, call_id: str, params: dict
    ) -> str:
        self.stop_live()
        console.print(f"\n[yellow]Tool:[/yellow] {name}")
        for k, v in params.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            console.print(f"  [dim]{k}:[/dim] {val_str}")

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._session.prompt("  Allow? [y/n/always] "),
        )
        response = response.strip().lower()
        if response in ("y", "yes"):
            return "y"
        elif response in ("a", "always"):
            return "always"
        return "n"

    async def request_user_input(self, question: str) -> str:
        self.stop_live()
        console.print(f"\n[cyan]Question:[/cyan] {question}")
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._session.prompt("  > "),
        )
        return response.strip()

    async def on_message_end(self, usage: TokenUsage) -> None:
        self.stop_live()
        if self._streaming_text:
            console.print()
        if usage.input_tokens or usage.output_tokens:
            console.print(
                f"[dim]tokens: {usage.input_tokens} in / {usage.output_tokens} out[/dim]"
            )


async def _handle_history(store: Store, args: str) -> None:
    """Handle /history command."""
    args = args.strip()
    if args:
        # Show conversation for specific task
        task = await store.get_task(args)
        if not task:
            console.print(f"[red]Task not found: {args}[/red]")
            return
        messages = await store.get_messages(args)
        console.print(f"\n[bold]Task:[/bold] {task.title or task.id}")
        console.print(f"[dim]Mode: {task.mode} | Status: {task.status.value}[/dim]\n")
        for msg in messages:
            role_color = {"user": "green", "assistant": "blue", "system": "yellow", "tool": "magenta"}
            color = role_color.get(msg.role.value, "white")
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            console.print(f"[{color}]{msg.role.value}:[/{color}] {content}")
    else:
        # List recent tasks
        tasks = await store.get_root_tasks(limit=20)
        if not tasks:
            console.print("[dim]No task history.[/dim]")
            return
        table = Table(title="Task History")
        table.add_column("ID", style="dim", max_width=8)
        table.add_column("Status")
        table.add_column("Mode")
        table.add_column("Title")
        table.add_column("Tokens", justify="right")
        for t in tasks:
            status_color = {
                "active": "green", "completed": "blue",
                "failed": "red", "cancelled": "yellow",
            }.get(t.status.value, "white")
            total_tokens = t.token_usage.input_tokens + t.token_usage.output_tokens
            table.add_row(
                t.id[:8],
                f"[{status_color}]{t.status.value}[/{status_color}]",
                t.mode,
                t.title or "(untitled)",
                f"{total_tokens:,}",
            )
        console.print(table)


async def _handle_export(store: Store, settings: Settings, args: str) -> None:
    """Handle /export command."""
    args = args.strip()
    if not args:
        console.print("[red]Usage: /export <task_id>[/red]")
        return

    parts = args.split()
    task_id = parts[0]
    include_children = "--tree" in parts

    try:
        data = await export_task(store, task_id, include_children=include_children)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return

    export_dir = os.path.join(settings.data_dir, "exports")
    os.makedirs(export_dir, exist_ok=True)
    filename = f"task-{task_id[:8]}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    filepath = os.path.join(export_dir, filename)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    console.print(f"Exported to {filepath}")


async def _handle_task(store: Store, task: Task, args: str) -> None:
    """Handle /task command."""
    args = args.strip()
    if args == "tree":
        await _print_task_tree(store, task, indent=0)
    else:
        console.print(f"[bold]Current Task:[/bold] {task.id[:8]}")
        console.print(f"  Title: {task.title}")
        console.print(f"  Mode: {task.mode}")
        console.print(f"  Status: {task.status.value}")
        total = task.token_usage.input_tokens + task.token_usage.output_tokens
        console.print(f"  Tokens: {total:,}")
        if task.todo_list:
            console.print("  Todo:")
            for item in task.todo_list:
                check = "[x]" if item.done else "[ ]"
                console.print(f"    {check} {item.text}")


async def _print_task_tree(store: Store, task: Task, indent: int) -> None:
    prefix = "  " * indent
    status_icon = {"active": "*", "completed": "+", "failed": "!", "pending": "-"}.get(task.status.value, "?")
    console.print(f"{prefix}({status_icon}) Task {task.id[:8]} [{task.mode}] — {task.title or '(untitled)'}")
    children = await store.get_children(task.id)
    for child in children:
        await _print_task_tree(store, child, indent + 1)


async def run_repl(settings: Settings) -> None:
    """Main REPL loop with full agent support."""
    settings.ensure_dirs()

    store = Store(settings.db_path)
    await store.initialize()

    try:
        provider = create_provider(settings.provider)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    # Set up skills
    skills_manager = SkillsManager(search_dirs=settings.skills_dirs)
    skills_manager.discover()

    # Set up tool registry with native, agent, and skill tools
    registry = ToolRegistry()
    for tool in get_all_native_tools():
        registry.register(tool)
    for tool in get_all_agent_tools():
        registry.register(tool)
    registry.register(SkillTool(skills_manager=skills_manager))

    # Prompt builder
    prompt_builder = PromptBuilder()

    model_info = provider.get_model_info()
    console.print(
        Panel(
            f"[bold]mini-agent[/bold] v0.1.0\n"
            f"Provider: {model_info.provider} / {model_info.model_id}\n"
            f"Mode: {settings.default_mode}\n"
            f"Tools: {len(registry.all_tools())} registered",
            border_style="blue",
        )
    )
    console.print(
        "[dim]Commands: /mode /tools /todo /task /history /export /quit[/dim]\n"
    )

    task = Task(
        id=new_id(),
        mode=settings.default_mode,
        status=TaskStatus.ACTIVE,
        title="Interactive session",
        working_directory=settings.working_directory,
    )
    await store.create_task(task)

    conversation: list[dict] = []

    history_path = f"{settings.data_dir}/repl_history"
    prompt_session = PromptSession(history=FileHistory(history_path))

    cli_callbacks = CLICallbacks(prompt_session)
    callbacks = AgentCallbacks(
        on_text_delta=cli_callbacks.on_text_delta,
        on_tool_call_start=cli_callbacks.on_tool_call_start,
        on_tool_call_end=cli_callbacks.on_tool_call_end,
        on_tool_approval_request=cli_callbacks.on_tool_approval_request,
        request_user_input=cli_callbacks.request_user_input,
        on_message_end=cli_callbacks.on_message_end,
    )

    agent = Agent(
        provider=provider,
        registry=registry,
        store=store,
        settings=settings,
        callbacks=callbacks,
    )

    while True:
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: prompt_session.prompt(f"[{task.mode}] > "),
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # --- CLI Commands ---
        if user_input.lower() in ("exit", "quit", "/quit"):
            console.print("[dim]Goodbye![/dim]")
            break

        if user_input.startswith("/mode"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                modes = list_modes()
                console.print("[bold]Available modes:[/bold]")
                for m in modes:
                    marker = " *" if m.slug == task.mode else ""
                    console.print(f"  {m.slug}{marker} — {m.when_to_use}")
            else:
                new_mode = parts[1].strip()
                try:
                    get_mode(new_mode)
                    task.mode = new_mode
                    await store.update_task(task)
                    console.print(f"Switched to [bold]{new_mode}[/bold] mode.")
                except KeyError as e:
                    console.print(f"[red]{e}[/red]")
            continue

        if user_input == "/todo":
            if task.todo_list:
                for item in task.todo_list:
                    check = "[x]" if item.done else "[ ]"
                    console.print(f"  {check} {item.text}")
            else:
                console.print("[dim]No todo items.[/dim]")
            continue

        if user_input == "/tools":
            mode_config = get_mode(task.mode)
            tools = registry.get_tools_for_mode(mode_config.tool_groups)
            console.print(f"[bold]Tools available in {task.mode} mode:[/bold]")
            for t in tools:
                console.print(f"  {t.name} — {t.description[:80]}")
            continue

        if user_input.startswith("/history"):
            args = user_input[len("/history"):].strip()
            await _handle_history(store, args)
            continue

        if user_input.startswith("/export"):
            args = user_input[len("/export"):].strip()
            await _handle_export(store, settings, args)
            continue

        if user_input.startswith("/task"):
            args = user_input[len("/task"):].strip()
            await _handle_task(store, task, args)
            continue

        # --- Agent Turn ---
        mode_config = get_mode(task.mode)
        available_tools = registry.get_tools_for_mode(mode_config.tool_groups)
        skill_summaries = skills_manager.get_summaries_for_mode(task.mode)
        system_prompt = prompt_builder.build(
            mode=mode_config,
            task=task,
            settings=settings,
            tools=available_tools,
            skills=skill_summaries,
        )

        cli_callbacks.start_live()
        try:
            await agent.run(
                task=task,
                user_message=user_input,
                conversation=conversation,
                system_prompt=system_prompt,
            )
        except Exception as e:
            cli_callbacks.stop_live()
            console.print(f"[red]Error:[/red] {e}")
            continue
        finally:
            cli_callbacks.stop_live()

    task.status = TaskStatus.COMPLETED
    await store.update_task(task)
    await store.close()


@click.group(invoke_without_command=True)
@click.option("--config", "-c", "config_path", default=None, help="Path to config file")
@click.pass_context
def main(ctx, config_path):
    """Mini-Agent: A modular AI agent framework."""
    if ctx.invoked_subcommand is None:
        settings = Settings.load(config_path)
        asyncio.run(run_repl(settings))


@main.command()
@click.option("--config", "-c", "config_path", default=None)
def chat(config_path):
    """Start interactive chat session."""
    settings = Settings.load(config_path)
    asyncio.run(run_repl(settings))


@main.command()
@click.argument("task_id")
@click.option("-o", "--output", default=None, help="Output file path")
@click.option("--tree", is_flag=True, help="Include child tasks")
@click.option("--config", "-c", "config_path", default=None)
def export(task_id, output, tree, config_path):
    """Export a task to JSON."""
    async def _export():
        settings = Settings.load(config_path)
        settings.ensure_dirs()
        store = Store(settings.db_path)
        await store.initialize()
        try:
            data = await export_task(store, task_id, include_children=tree)
            if output:
                with open(output, "w") as f:
                    json.dump(data, f, indent=2)
                click.echo(f"Exported to {output}")
            else:
                click.echo(json.dumps(data, indent=2))
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
        finally:
            await store.close()

    asyncio.run(_export())


if __name__ == "__main__":
    main()
