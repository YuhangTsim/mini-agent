# CLAUDE.md — Open-Agent Worktree

This file provides guidance to Claude Code when working with the `open-agent` worktree.

## Plan Management Rules

- **Save new plans to** `.claude/plans/`
- **Archive old plans** to `.claude/plans/archived/` with date prefix: `YYYY-MM-DD_original-name.md`
- **Keep only active plans** in the main plans folder
- When revising a plan, archive the old version and create a new dated filename

## Repository Context

This is a **git worktree** of the `minimal-agent` bare repository. Open-Agent is a multi-agent framework that coexists with `roo-agent` (mode-based) in a dual-framework architecture.

**Source location:** `src/open_agent/`

## Quick Start

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run (from unified CLI)
export OPENAI_API_KEY="sk-..."
mini-agent --open           # Run open-agent multi-agent mode

# Or directly
open-agent
```

## Development Commands

```bash
# Test
pytest tests/ -v
pytest tests/test_bus.py -v
pytest -x

# Lint & Format
ruff check . --fix
ruff format .

# Type checking
mypy src/open_agent
```

## Architecture

Open-Agent is a **multi-agent event-driven framework**. Instead of one agent switching modes, multiple specialized agents each run their own session with their own LLM config and tool set.

### Core Subsystems

| Component | Purpose |
|-----------|---------|
| **bus/** | Typed async EventBus (pub/sub + queue streams) |
| **agents/** | BaseAgent ABC + specialized agents (orchestrator, explorer, librarian, oracle, designer, fixer) |
| **core/session.py** | SessionProcessor: LLM→tool loop for one agent |
| **core/delegation.py** | DelegationManager: validates + routes to child SessionProcessor |
| **core/background.py** | BackgroundTaskManager: fire-and-forget with semaphore |
| **core/app.py** | OpenAgentApp: wires everything, lifecycle management |
| **providers/** | BaseProvider + OpenAI implementation + ProviderRegistry |
| **tools/** | ToolRegistry, PermissionChecker, native tools, delegation tools |
| **hooks/** | BaseHook + HookRegistry (before/after tool, message transform) |
| **prompts/** | PromptBuilder with agent-specific prompt composition |
| **persistence/** | Async SQLite (Session, AgentRun, Message, ToolCall) |
| **config/** | TOML settings + AgentConfig Pydantic schema |
| **api/** | AgentService + FastAPI HTTP API |
| **cli/** | Click REPL with bus-based callbacks |

### Directory Structure

```
src/open_agent/
├── agents/           # Agent implementations
│   ├── base.py       # BaseAgent ABC
│   ├── orchestrator.py   # Delegation workflow
│   ├── explorer.py   # Search specialist
│   ├── librarian.py  # Documentation specialist
│   ├── oracle.py     # Architecture advisor
│   ├── designer.py   # UI/UX specialist
│   ├── fixer.py      # Implementation specialist
│   └── registry.py   # AgentRegistry
├── bus/              # Event bus system
│   ├── bus.py        # EventBus implementation
│   └── events.py     # Event type definitions
├── core/             # Core orchestration
│   ├── app.py        # OpenAgentApp
│   ├── session.py    # SessionProcessor
│   ├── delegation.py # DelegationManager
│   └── background.py # BackgroundTaskManager
├── providers/        # LLM providers
│   ├── base.py       # BaseProvider
│   ├── openai.py     # OpenAI implementation
│   └── registry.py   # ProviderRegistry
├── tools/            # Tool system
│   ├── base.py       # BaseTool, ToolRegistry
│   ├── permissions.py # PermissionChecker
│   ├── native/       # Native tools (file_ops, search, command)
│   └── agent/        # Delegation tools
├── prompts/          # Prompt building
│   ├── builder.py    # PromptBuilder
│   └── sections/     # Prompt sections (role, rules, tools, etc.)
├── persistence/      # SQLite storage
│   ├── store.py      # Store class
│   └── models.py     # Pydantic models
├── config/           # Configuration
│   ├── settings.py   # Settings loader
│   └── agents.py     # AgentConfig, PermissionRule
├── api/              # HTTP API
│   ├── service.py    # AgentService
│   └── http/         # FastAPI server
├── cli/              # CLI
│   └── app.py        # Click REPL
├── hooks/            # Hook system (minimal)
│   ├── base.py       # BaseHook, HookPoint
│   └── registry.py   # HookRegistry
└── skills/           # Skills system (placeholder)
    └── __init__.py
```

## Specialized Agents

| Agent | Role | Delegates To |
|-------|------|--------------|
| **orchestrator** | Task analysis, workflow management, delegation decisions | All specialists |
| **explorer** | Parallel search specialist (glob, grep, AST queries) | — |
| **librarian** | Documentation & API research (fetches latest docs) | — |
| **oracle** | Strategic advisor for architecture decisions | explorer |
| **designer** | UI/UX specialist for polished experiences | — |
| **fixer** | Fast implementation specialist for well-defined tasks | — |

## Workflow (Orchestrator)

The orchestrator follows a 6-step workflow:

1. **Understand** — Parse explicit requirements + implicit needs
2. **Path Analysis** — Evaluate approach by quality, speed, cost, reliability
3. **Delegation Check** — Review specialists before acting
4. **Parallelize** — Run independent tasks simultaneously when possible
5. **Execute** — Delegate or implement based on analysis
6. **Verify** — Confirm solution meets requirements

## Code Conventions

- **Python:** 3.11+, async-first (asyncio + aiosqlite)
- **Linting:** Ruff for linting and formatting, line length 100
- **Testing:** pytest with `asyncio_mode = "auto"`
- **Types:** Pydantic v2 for data validation, dataclasses for internal models
- **Type hints:** Required throughout

## Key Patterns

### Agent Configuration

```python
from open_agent.config.agents import AgentConfig

config = AgentConfig(
    role="explorer",
    name="Explorer",
    model="gpt-4o-mini",
    allowed_tools=["search_files", "read_file"],
    can_delegate_to=[],  # Leaf agent (no delegation)
)
```

### Tool Registration

Tools are registered in `OpenAgentApp.initialize()`:
- Native tools from `tools.native.get_all_native_tools()`
- Delegation tools from `tools.agent.get_all_delegation_tools()`

### Session Processing

```python
processor = SessionProcessor(
    agent=agent,
    provider=provider,
    tool_registry=tool_registry,
    permission_checker=permission_checker,
    # ... other dependencies
)
result = await processor.process(agent_run=run, user_message=msg)
```

## Configuration

Configuration is loaded from `~/.mini-agent/config.toml` (shared with roo-agent):

```toml
[provider]
name = "openai"
model = "gpt-4o"

[open_agent]
default_agent = "orchestrator"
max_delegation_depth = 3

[open_agent.background]
max_concurrent = 3

[open_agent.agents.orchestrator]
model = "gpt-4o"
temperature = 0.0
```

## Dual Framework Notes

- **roo-agent**: Mode-based (code, plan, ask, debug, orchestrator) — default in `mini-agent`
- **open-agent**: Multi-agent event-driven — launched via `mini-agent --open`
- Both share unified configuration in `~/.mini-agent/config.toml`
- Each has independent source trees but common persistence layer
