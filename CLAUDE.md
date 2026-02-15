# CLAUDE.md — Open-Agent

This file provides guidance to Claude Code when working with the `open-agent` worktree.

## Repository Layout

This is a **git worktree** of the `minimal-agent` bare repository. Open-Agent is a separate framework that shares no imports with `mini_agent`.

Source lives in `src/open_agent/`.

## Development Commands

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run
export OPENAI_API_KEY="sk-..."
open-agent

# Test
pytest
pytest tests/test_bus.py -v
pytest -x

# Lint & Format
ruff check . --fix
ruff format .
```

## Architecture

Open-Agent is a multi-agent framework. Instead of one agent switching modes, multiple specialized agents each run their own session with their own LLM config and tool set.

Key layers in `src/open_agent/`:

- **bus/** — Typed async EventBus (pub/sub + queue streams)
- **agents/** — BaseAgent ABC + concrete agents (orchestrator, coder, explorer, planner, debugger, reviewer)
- **core/session.py** — SessionProcessor: LLM→tool loop for one agent
- **core/delegation.py** — DelegationManager: validates + routes to child SessionProcessor
- **core/background.py** — BackgroundTaskManager: fire-and-forget with semaphore
- **core/app.py** — OpenAgentApp: wires everything, lifecycle
- **providers/** — BaseProvider + OpenAI implementation
- **tools/** — BaseTool, ToolRegistry, PermissionChecker, native tools, delegation tools
- **hooks/** — BaseHook + HookRegistry (before/after tool, message transform)
- **plugins/** — PluginBase ABC + dynamic discovery
- **persistence/** — Async SQLite (Session, AgentRun, Message, ToolCall)
- **prompts/** — PromptBuilder with agent-specific prompt composition
- **config/** — TOML settings + AgentConfig Pydantic schema
- **api/** — AgentService + FastAPI HTTP API
- **cli/** — Click REPL with bus-based callbacks

## Code Conventions

- Python 3.11+, async-first (asyncio + aiosqlite)
- Ruff for linting and formatting, line length 100
- pytest with `asyncio_mode = "auto"`
- Pydantic v2 for data validation, dataclasses for internal models
- Type hints throughout
