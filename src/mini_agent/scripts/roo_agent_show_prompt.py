"""CLI command to display roo-agent prompts."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from roo_agent.core.mode import get_mode, list_modes
from roo_agent.prompts.builder import PromptBuilder
from roo_agent.tools.base import ToolRegistry
from roo_agent.persistence.models import Task
from roo_agent.config.settings import Settings


def get_available_modes() -> dict[str, str]:
    """Get all available modes with their descriptions."""
    modes: dict[str, str] = {}
    for mode in list_modes():
        modes[mode.slug] = mode.when_to_use
    return modes


def build_mode_prompt(mode_name: str) -> str | None:
    """Build the full prompt for a mode.

    Returns:
        The prompt string if successful, None if mode not found.
    """
    try:
        mode_config = get_mode(mode_name)
    except KeyError:
        return None

    settings = Settings.load()

    # Get tools for this mode
    tool_registry = ToolRegistry()

    # Get tools for the mode's tool groups
    tools = tool_registry.get_tools_for_mode(mode_config.tool_groups)

    # Create a dummy task (prompt needs it but content won't affect role/rules)
    task = Task(
        id="sample-task",
        description="Sample task for prompt display"
    )
    task.working_directory = os.getcwd()

    # Build prompt
    builder = PromptBuilder()
    prompt = builder.build(
        mode=mode_config,
        task=task,
        settings=settings,
        tools=tools,
        skills=[]
    )

    return prompt


def list_modes_func() -> None:
    """Print list of available modes."""
    print("Available roo-agent modes:")
    print()

    modes = get_available_modes()
    if not modes:
        print("  No modes found. Run 'uv pip install -e \".[dev]\"' to ensure all dependencies are installed.")
        return

    for name in sorted(modes.keys()):
        desc = modes[name]
        print(f"  {name}")
        # Print first line of description indented
        if desc:
            first_line = desc.split('\n')[0][:80]
            print(f"    {first_line}...")
    print()
    print(f"Use --mode <name> to see the full prompt for a specific mode.")


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="roo-agent-show-prompt",
        description="Display the full prompt for a roo-agent mode."
    )
    parser.add_argument(
        "--mode",
        type=str,
        help="Name of the mode to display prompt for"
    )

    args = parser.parse_args(argv)

    if args.mode is None:
        list_modes_func()
        return 0

    prompt = build_mode_prompt(args.mode)

    if prompt is None:
        print(f"Error: Unknown mode '{args.mode}'", file=sys.stderr)
        print(file=sys.stderr)
        list_modes_func()
        return 1

    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
