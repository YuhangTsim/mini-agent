# Mini-Agent

A modular, controllable AI agent framework in Python. Provider-agnostic (starting with OpenAI), with task hierarchies, full persistence, and a clean API layer decoupled from any frontend.

## Quick Start

```bash
# Install with uv
cd main/
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # core + dev tools
uv pip install -e ".[dev,api]"      # with HTTP API support

# Set your API key
export OPENAI_API_KEY="sk-..."

# Run the interactive REPL
mini-agent

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

## Features

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
src/mini_agent/
├── cli/                 # Interactive CLI (click + rich + prompt_toolkit)
│   └── app.py           # REPL entry point
├── core/                # Core engine
│   ├── agent.py         # Agent loop (LLM → tool → approval → result)
│   └── mode.py          # Mode definitions & switching
├── providers/           # LLM provider abstraction
│   ├── base.py          # Abstract provider interface
│   ├── openai.py        # OpenAI implementation
│   └── registry.py      # Provider factory
├── tools/               # Tool system
│   ├── base.py          # BaseTool, ToolRegistry, approval system
│   ├── native/          # Built-in tools (file_ops, search, command, todo, interaction, skill)
│   └── agent/           # Agent tools (new_task, switch_mode, attempt_completion)
├── skills/              # Skills system
│   ├── manager.py       # Discovery, loading, mode filtering
│   ├── loader.py        # Markdown/frontmatter parser
│   └── builtin/         # Built-in skill files
├── prompts/             # Sectional prompt system
│   ├── builder.py       # Dynamic prompt composer
│   └── sections/        # role, tools, skills, rules, system_info
├── persistence/         # SQLite persistence
│   ├── models.py        # Task, Message, ToolCall, TokenUsage
│   ├── store.py         # Async SQLite CRUD
│   └── export.py        # JSON export
├── api/                 # Frontend-agnostic API layer
│   ├── service.py       # AgentService (business logic)
│   ├── events.py        # Event bus for real-time updates
│   └── http/            # FastAPI HTTP server
│       ├── server.py    # App factory + uvicorn runner
│       ├── routes/      # REST + SSE endpoints
│       ├── schemas.py   # Pydantic request/response models
│       └── middleware.py # CORS configuration
└── config/
    └── settings.py      # TOML config loading
```

## CLI Commands

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
