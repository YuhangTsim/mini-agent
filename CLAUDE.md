# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This repo uses a **bare repository with git worktrees**. The actual source code lives in worktree directories (e.g., `main/`, `feature-example/`), not at the repo root. The bare repo is at `minimal-agent.git/`.

```bash
git -C minimal-agent.git worktree list                              # list worktrees
git -C minimal-agent.git worktree add -b feature-name ../feature-name main  # create new
```

The main source tree is in `main/`.

## Development Commands

All commands should be run from inside a worktree directory (e.g., `main/`).

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # core + dev tools
uv pip install -e ".[dev,pdf]"      # with PDF support
uv pip install -e ".[dev,api]"      # with API support

# Run
export OPENAI_API_KEY="sk-..."
mini-agent                          # interactive REPL

# Test
pytest                              # all tests
pytest tests/test_foo.py            # single file
pytest tests/test_foo.py::test_bar  # single test
pytest -x                           # stop on first failure

# Lint & Format
ruff check . --fix
ruff format .
```

## Architecture

Mini-Agent is a modular AI agent framework. The core loop is: **LLM call → tool selection → approval check → tool execution → result fed back to LLM**.

Key layers in `src/mini_agent/`:

- **core/agent.py** — Main agent loop orchestrating the LLM-tool cycle. `Agent` class coordinates all subsystems via `AgentCallbacks` for UI events.
- **core/mode.py** — Five modes (`code`, `plan`, `ask`, `debug`, `orchestrator`) each restricting which tool groups are available.
- **providers/** — Abstract `BaseProvider` with streaming `StreamEvent` protocol. OpenAI implementation in `openai.py`. Add new LLM backends by implementing `BaseProvider`.
- **tools/base.py** — `BaseTool` abstract class, `ToolRegistry` for discovery/filtering by mode, `ApprovalPolicy` enum controlling per-tool approval behavior.
- **tools/native/** — 8 built-in tools (file read/write/edit, search, list, command exec, todo, ask followup).
- **tools/agent/** — Agent-level tools (new_task, switch_mode, attempt_completion) for task delegation.
- **persistence/** — Async SQLite via aiosqlite. `Task` model supports parent/child hierarchy. All messages and tool calls are persisted.
- **prompts/builder.py** — Composes system prompts from modular sections (role, tools, skills, rules, system_info, objective).
- **skills/** — Markdown files with YAML frontmatter, auto-discovered from `.mini-agent/skills/`, `~/.mini-agent/skills/`, and `skills/builtin/`. Mode-scoped.
- **api/service.py** — `AgentService` is the frontend-agnostic business logic layer; CLI and HTTP API both use it.
- **config/settings.py** — TOML config from `.mini-agent/config.toml`. API keys resolved from environment variables.

## Code Conventions

- Python 3.11+, async-first (asyncio + aiosqlite)
- Ruff for linting and formatting, line length 100
- pytest with `asyncio_mode = "auto"` — async test functions are auto-detected
- Pydantic v2 for data validation, dataclasses for internal models
- Type hints throughout
