"""CLI command to display open-agent prompts."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

# Import all agent classes directly
from open_agent.agents.orchestrator import OrchestratorAgent
from open_agent.agents.explorer import ExplorerAgent
from open_agent.agents.librarian import LibrarianAgent
from open_agent.agents.oracle import OracleAgent
from open_agent.agents.designer import DesignerAgent
from open_agent.agents.fixer import FixerAgent


AGENT_CLASSES = {
    "orchestrator": OrchestratorAgent,
    "explorer": ExplorerAgent,
    "librarian": LibrarianAgent,
    "oracle": OracleAgent,
    "designer": DesignerAgent,
    "fixer": FixerAgent,
}


def get_available_agents() -> dict[str, str]:
    """Get all available agents with their descriptions."""
    agents: dict[str, str] = {}
    for slug, agent_class in AGENT_CLASSES.items():
        # Instantiate to get the full role definition
        agent = agent_class()
        agents[slug] = agent.config.role_definition
    return agents


def build_agent_prompt(agent_name: str) -> str | None:
    """Build the full prompt for an agent.

    Returns:
        The prompt string if successful, None if agent not found.
    """
    if agent_name not in AGENT_CLASSES:
        return None

    # Instantiate the agent to get proper configuration
    agent_class = AGENT_CLASSES[agent_name]
    agent = agent_class()

    # Build prompt using the agent's own method
    prompt = agent.get_system_prompt(context={"working_directory": os.getcwd()})

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
