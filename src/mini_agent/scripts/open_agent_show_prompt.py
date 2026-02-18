"""CLI command to display open-agent prompts."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from open_agent.prompts.builder import PromptBuilder
from open_agent.tools.base import ToolRegistry
from open_agent.config.settings import Settings, DEFAULT_AGENTS
from open_agent.tools.native import get_all_native_tools


def get_available_agents() -> dict[str, str]:
    """Get all available agents with their descriptions."""
    settings = Settings()
    agents: dict[str, str] = {}
    for slug, config in settings.agents.items():
        agents[slug] = config.role_definition
    return agents


def build_agent_prompt(agent_name: str) -> str | None:
    """Build the full prompt for an agent.

    Returns:
        The prompt string if successful, None if agent not found.
    """
    settings = Settings()

    if agent_name not in settings.agents:
        return None

    agent_config = settings.agents[agent_name]

    # Create tool registry and register native tools
    tool_registry = ToolRegistry()
    for tool in get_all_native_tools():
        tool_registry.register(tool)

    # Get tools for this agent
    allowed_tools = []
    for tool_name in agent_config.allowed_tools:
        tool = tool_registry.get(tool_name)
        if tool:
            allowed_tools.append(tool)

    # Build prompt
    builder = PromptBuilder()
    prompt = builder.build(
        agent_config=agent_config,
        working_directory=os.getcwd(),
        tools=allowed_tools
    )

    return prompt


def list_agents() -> None:
    """Print list of available agents."""
    print("Available open-agent agents:")
    print()

    agents = get_available_agents()
    if not agents:
        print("  No agents found.")
        return

    for name in sorted(agents.keys()):
        desc = agents[name]
        print(f"  {name}")
        # Print first line of description indented
        if desc:
            first_line = desc.split('\n')[0][:80]
            print(f"    {first_line}...")
    print()
    print(f"Use --agent <name> to see the full prompt for a specific agent.")


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="open-agent-show-prompt",
        description="Display the full prompt for an open-agent agent."
    )
    parser.add_argument(
        "--agent",
        type=str,
        help="Name of the agent to display prompt for"
    )

    args = parser.parse_args(argv)

    if args.agent is None:
        list_agents()
        return 0

    prompt = build_agent_prompt(args.agent)

    if prompt is None:
        print(f"Error: Unknown agent '{args.agent}'", file=sys.stderr)
        print(file=sys.stderr)
        list_agents()
        return 1

    print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
