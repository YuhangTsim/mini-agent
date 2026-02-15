# Mini-Agent

A dual-framework AI agent platform featuring **roo-agent** (mode-based, Roo Code philosophy) and **open-agent** (multi-agent event-driven). Provider-agnostic with task hierarchies, full persistence, and a clean API layer.

## Quick Start

```bash
# Install with uv
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # core + dev tools
uv pip install -e ".[dev,api]"      # with HTTP API support

# Set your API key
export OPENAI_API_KEY="sk-..."

# Run the interactive REPL (defaults to roo-agent)
mini-agent

# Or use open-agent (multi-agent)
mini-agent --open

# Or start the HTTP API server (requires API extras)
uv pip install -e ".[dev,api]"
mini-agent serve --port 8080
```

### Run the Web UI

```bash
# Terminal 1: Start the backend API server
cd main/
uv run mini-agent serve --port 8080

# Terminal 2: Start the frontend dev server
cd ui/
npm install && npm run dev
# Opens http://localhost:5173
```

See [ui/README.md](ui/README.md) for full web UI documentation.

## Dual Framework Architecture

Mini-Agent provides two distinct agent paradigms:

### Roo-Agent (Default)
**Mode-based single agent** following Roo Code philosophy. One powerful agent with switchable modes (code, plan, ask, debug, orchestrator). Best for focused tasks with Roo-style code editing and diff viewing.

### Open-Agent
**Multi-agent event-driven system** with specialized agents coordinated via event bus. Best for complex workflows requiring multiple specialist agents working together.

## Features

- **Dual framework** — roo-agent (mode-based) + open-agent (multi-agent) in one package
- **Multi-mode system** — code, plan, ask, debug, orchestrator modes with per-mode tool access
- **11 built-in tools** — file ops, search, command execution, todo lists, user interaction, task management
- **Task hierarchy** — parent/child tasks with independent conversations and result propagation
- **Full persistence** — SQLite-backed storage for tasks, messages, and tool call audit logs
- **Skills system** — Markdown skill files with YAML frontmatter, mode-scoped, auto-discovered
- **Configurable approval** — per-tool approval policies (auto_approve, always_ask, ask_once, deny)
- **Streaming responses** — real-time token streaming with rich terminal formatting
- **HTTP API + Web UI** — FastAPI server with SSE streaming and React frontend
- **JSON export** — export tasks with full conversation history and token usage
- **Provider-agnostic** — abstract provider interface, easy to add new LLM backends

## Project Structure

```
src/
├── roo_agent/           # Mode-based agent framework (formerly mini_agent)
│   ├── cli/             # Interactive CLI (click + rich + prompt_toolkit)
│   ├── core/            # Core engine (agent.py, mode.py)
│   ├── providers/       # LLM provider abstraction
│   ├── tools/           # Tool system (native + agent tools)
│   ├── skills/          # Skills system
│   ├── prompts/         # Sectional prompt system
│   ├── persistence/     # SQLite persistence
│   ├── api/             # FastAPI HTTP server
│   └── config/          # TOML config loading
├── open_agent/          # Multi-agent event-driven framework
│   ├── cli/             # Open-agent CLI
│   ├── core/            # Session, orchestration
│   ├── agents/          # Specialized agents
│   ├── bus/             # Event bus system
│   ├── providers/       # LLM providers
│   ├── tools/           # Tool registry
│   └── persistence/     # Storage layer
└── minimal_agent/       # Unified entry point
    ├── __init__.py      # Package exports
    └── cli.py           # Main CLI (defaults to roo-agent)
```

## CLI Usage

### Main Entry Point

```bash
# Default: roo-agent (mode-based)
mini-agent

# Use open-agent (multi-agent event-driven)
mini-agent --open

# Direct framework commands (bypass main CLI)
roo-agent                    # Mode-based agent
open-agent                   # Multi-agent system
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--open` | Use open-agent instead of roo-agent (default) |
| `--config PATH` | Path to config file |
| `--mode MODE` | Set agent mode (roo-agent only, default: coder) |

### Interactive Commands (within REPL)

| Command | Description |
|---------|-------------|
| `/mode [name]` | List modes or switch to a mode |
| `/model [list\|name]` | Show current model, list available, or switch |
| `/tools` | List tools available in current mode |
| `/todo` | Show current task's todo list |
| `/task [tree]` | Show current task info or task tree |
| `/history [task_id]` | List recent tasks or show a task's conversation |
| `/export <task_id>` | Export task to JSON file |
| `/quit` | Exit |

## HTTP API Server

The `serve` command starts a FastAPI server exposing the agent over HTTP with Server-Sent Events for streaming.

```bash
# Install API dependencies
uv pip install -e ".[api]"

# Start the server
mini-agent serve --port 8080
```

**API endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/tasks` | Create a new task |
| `GET` | `/api/tasks` | List tasks |
| `GET` | `/api/tasks/{id}` | Get task details |
| `DELETE` | `/api/tasks/{id}` | Cancel a task |
| `POST` | `/api/tasks/{id}/messages` | Send a message |
| `GET` | `/api/tasks/{id}/messages` | Get message history |
| `GET` | `/api/tasks/{id}/stream` | SSE stream for real-time events |
| `POST` | `/api/tasks/{id}/mode` | Switch task mode |
| `GET` | `/api/modes` | List available modes |
| `POST` | `/api/approvals/{id}` | Respond to tool approval |
| `POST` | `/api/inputs/{id}` | Respond to user input request |

### Web UI

A React frontend lives in `ui/`. For development, run the API server and Vite dev server separately:

```bash
# Terminal 1: API server
mini-agent serve --port 8080

# Terminal 2: Vite dev server (proxies /api to :8080)
cd ui && npm install && npm run dev
```

For production, build the UI and serve it from the API server:

```bash
cd ui && npm run build
mini-agent serve --port 8080 --static-dir ../ui/dist
```

## Modes

| Mode | Tools | Purpose |
|------|-------|---------|
| `code` | read, edit, command | Writing and implementing code |
| `plan` | read, edit (.md only) | Planning and design |
| `ask` | read | Q&A without modifications |
| `debug` | read, edit, command | Troubleshooting and bug fixing |
| `orchestrator` | agent tools only | Task delegation |

## Choosing a Framework

| | Roo-Agent (Default) | Open-Agent |
|---|---------------------|------------|
| **Paradigm** | Single agent with switchable modes | Multiple specialized agents |
| **Architecture** | Mode-based (Roo Code style) | Event-driven with event bus |
| **Best for** | Focused tasks, code editing | Complex multi-domain workflows |
| **Strengths** | Deep tool integration, Roo-style diffs | Hierarchical delegation, background tasks |
| **CLI** | `mini-agent` | `mini-agent --open` |

**Use roo-agent when:** You want a single agent that deeply understands context and can switch between coding, planning, debugging, and asking modes with Roo Code-style interactions.

**Use open-agent when:** You have complex tasks requiring multiple specialists (coder, researcher, reviewer) working together with coordinated event-driven communication.

## Configuration

Create `.mini-agent/config.toml` in your project:

```toml
default_mode = "code"

[provider]
name = "openai"
model = "gpt-4o"
max_tokens = 4096
temperature = 0.0

[tool_approval]
read_file = "auto_approve"
search_files = "auto_approve"
list_files = "auto_approve"
write_file = "always_ask"
execute_command = "always_ask"
"*" = "ask_once"
```

### Providers

Mini-Agent works with OpenAI and any OpenAI-compatible API. Set `base_url` to point to a compatible endpoint — the OpenAI client is used under the hood.

API keys are resolved in order: `api_key` in config → `<NAME>_API_KEY` environment variable. Local providers that don't require authentication can omit the key entirely.

You can optionally set `max_context` and `max_output` to specify the model's token limits (defaults to 128k context / 4096 output when not set).

**OpenAI** (default):

```toml
[provider]
name = "openai"
model = "gpt-4o"
```

```bash
export OPENAI_API_KEY="sk-..."
```

**Ollama** (local):

```toml
[provider]
name = "ollama"
model = "llama3"
base_url = "http://localhost:11434/v1"
max_context = 8192
```

**OpenRouter**:

```toml
[provider]
name = "openrouter"
model = "anthropic/claude-sonnet-4-20250514"
base_url = "https://openrouter.ai/api/v1"
```

```bash
export OPENROUTER_API_KEY="or-..."
```

**Any OpenAI-compatible API** (vLLM, LiteLLM, Together, etc.):

```toml
[provider]
name = "together"
model = "meta-llama/Llama-3-70b-chat-hf"
base_url = "https://api.together.xyz/v1"
max_context = 8192
max_output = 4096
```

## Skills

Skills are markdown files with YAML frontmatter placed in `.mini-agent/skills/` or `~/.mini-agent/skills/`:

```markdown
---
name: commit
description: Use when the user wants to create a git commit
modes: [code, debug]
---

## Instructions
1. Run `git status` to see changes
2. Draft a commit message
...
```

## Repository Setup

This repository uses a **bare repository with worktrees** setup for working on multiple features simultaneously.

### Structure

```
minimal-agent/
├── minimal-agent.git/     # Bare repository (central storage)
├── main/                  # Worktree for main branch (Python backend + CLI)
├── ui/                    # Web UI (React + TypeScript + Vite)
├── feature-example/       # Worktree for feature development
└── ...                    # Additional worktrees as needed
```

### Worktrees

| Path | Branch | Purpose |
|------|--------|---------|
| `minimal-agent.git/` | (bare) | Central repository - do not edit directly |
| `main/` | `main` | Stable/main development |
| `feature-example/` | `feature-example` | Example feature branch |

### Common Commands

```bash
# Navigate to bare repo
cd minimal-agent.git

# List all worktrees
git worktree list

# Create a new worktree for a feature
git worktree add -b feature-name ../feature-name main

# Remove a worktree when done
git worktree remove ../feature-name

# Prune stale worktree references
git worktree prune
```

### Benefits

- Work on multiple branches simultaneously without switching
- No stashing or context switching needed
- Each feature gets its own isolated directory
- All worktrees share the same git history

## License

(To be determined)
