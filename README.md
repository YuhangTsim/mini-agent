# Mini-Agent

A dual-framework AI agent platform featuring **roo-agent** (mode-based, Roo Code philosophy) and **open-agent** (multi-agent event-driven). Both agents share a unified configuration and can be launched from a single CLI entry point.

## Quick Start

```bash
# Install with uv
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"          # core + dev tools
uv pip install -e ".[dev,api]"      # with HTTP API support

# Interactive configuration wizard (first time setup)
mini-agent --configure

# Or run directly - will prompt for configuration if not set up
export OPENAI_API_KEY="sk-..."
mini-agent                          # Defaults to roo-agent

# Run open-agent (multi-agent)
mini-agent --open
```

## First-Time Configuration

The interactive wizard configures both agents at once:

```bash
mini-agent --configure
```

This creates `~/.mini-agent/config.toml` with:
- **Provider settings** (OpenAI, OpenRouter, Ollama, or OpenAI-compatible)
- **Model selection** with presets for each provider
- **API key** (saved to config or read from environment variable)
- **Open-agent settings** (default agents, delegation depth, etc.)

### Supported Providers

| Provider | Description | Environment Variable |
|----------|-------------|---------------------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-3.5 | `OPENAI_API_KEY` |
| **OpenRouter** | Claude, GPT-4, Gemini, and more | `OPENROUTER_API_KEY` |
| **Ollama** | Local models (Llama, Mistral, etc.) | None (local) |
| **OpenAI-Compatible** | Together, vLLM, custom endpoints | Varies |

### Manual Configuration

Create `~/.mini-agent/config.toml`:

```toml
# Shared provider configuration
[provider]
name = "openai"                              # or "openrouter", "ollama", "custom"
model = "gpt-4o"
base_url = "https://api.openai.com/v1"       # Optional, for custom endpoints
# api_key = "sk-..."                         # Optional, or use env var

# Open-agent specific settings
[open_agent]
default_agent = "orchestrator"
max_delegation_depth = 3

[open_agent.background]
max_concurrent = 3

# Agent-specific configurations
[open_agent.agents.orchestrator]
model = "gpt-4o"
temperature = 0.0

[open_agent.agents.explorer]
model = "gpt-4o-mini"

# Tool approval policies (shared)
[tool_approval]
read_file = "auto_approve"
search_files = "auto_approve"
write_file = "always_ask"
execute_command = "always_ask"
```

## CLI Usage

### Main Entry Point (Unified)

```bash
# Interactive configuration wizard
mini-agent --configure
mini-agent configure --global      # Global config (~/.mini-agent/)
mini-agent configure --force       # Reconfigure even if exists

# Run roo-agent (default) - mode-based single agent
mini-agent
mini-agent --mode coder            # Specific mode: code, plan, ask, debug

# Run open-agent - multi-agent event-driven
mini-agent --open

# Use custom config file
mini-agent --config /path/to/config.toml
mini-agent --open --config /path/to/config.toml

# Show version
mini-agent version
```

### Legacy Direct Commands

```bash
# Direct access to each framework
roo-agent                    # Mode-based agent
roo-agent configure          # Configure roo-agent specifically

open-agent                   # Multi-agent system  
open-agent chat              # Interactive chat
```

### Interactive Commands (REPL)

**Roo-Agent:**
| Command | Description |
|---------|-------------|
| `/mode [name]` | Switch mode or list modes |
| `/model [name]` | Switch model or list models |
| `/tools` | List available tools |
| `/history [task_id]` | Show task history |
| `/export <task_id>` | Export task to JSON |
| `/quit` | Exit |

**Open-Agent:**
| Command | Description |
|---------|-------------|
| `/agents` | List registered agents |
| `/tools` | List available tools |
| `/help` | Show help |
| `exit` or `quit` | Exit |

## Dual Framework Architecture

### Roo-Agent (Default)
**Mode-based single agent** following Roo Code philosophy. One powerful agent with switchable modes:

- **code** — Code editing, file operations, command execution
- **plan** — Task planning and architecture design  
- **ask** — Questions and explanations
- **debug** — Debugging and troubleshooting
- **orchestrator** — Task delegation and coordination

Best for focused tasks with Roo-style code editing and diff viewing.

### Open-Agent
**Multi-agent event-driven system** with specialized agents coordinated via event bus:

| Agent | Purpose | Can Delegate To |
|-------|---------|-----------------|
| **orchestrator** | Task analysis and delegation | All specialists |
| **explorer** | File/code exploration | — |
| **librarian** | Documentation & research | — |
| **oracle** | Architecture decisions | explorer |
| **designer** | UI/UX design | — |
| **fixer** | Implementation & debugging | — |

Best for complex workflows requiring multiple specialists working together.

## Choosing a Framework

| | Roo-Agent (Default) | Open-Agent |
|---|---------------------|------------|
| **Paradigm** | Single agent with switchable modes | Multiple specialized agents |
| **Architecture** | Mode-based (Roo Code style) | Event-driven with event bus |
| **Best for** | Focused tasks, code editing | Complex multi-domain workflows |
| **Strengths** | Deep tool integration, Roo-style diffs | Hierarchical delegation, background tasks |
| **CLI** | `mini-agent` | `mini-agent --open` |

## Features

- **Dual framework** — roo-agent (mode-based) + open-agent (multi-agent) in one package
- **Unified configuration** — Single config file works for both agents
- **Interactive wizard** — Easy first-time setup with provider selection
- **Multi-mode system** — code, plan, ask, debug, orchestrator modes with per-mode tool access
- **11 built-in tools** — file ops, search, command execution, todo lists, user interaction, task management
- **Task hierarchy** — parent/child tasks with independent conversations and result propagation
- **Full persistence** — SQLite-backed storage for tasks, messages, and tool call audit logs
- **Skills system** — Markdown skill files with YAML frontmatter, mode-scoped, auto-discovered
- **Configurable approval** — per-tool approval policies (auto_approve, always_ask, ask_once, deny)
- **Streaming responses** — real-time token streaming with rich terminal formatting
- **HTTP API + Web UI** — FastAPI server with SSE streaming and React frontend
- **JSON export** — export tasks with full conversation history and token usage
- **Provider-agnostic** — OpenAI, OpenRouter, Ollama, and any OpenAI-compatible API

## Project Structure

```
src/
├── mini_agent/          # Unified entry point
│   ├── __init__.py      # Package exports
│   └── cli.py           # Main CLI with config wizard
├── roo_agent/           # Mode-based agent framework
│   ├── cli/             # Interactive CLI (click + rich + prompt_toolkit)
│   │   ├── app.py       # Main REPL
│   │   └── config_wizard.py  # Configuration wizard
│   ├── core/            # Core engine (agent.py, mode.py)
│   ├── providers/       # LLM provider abstraction
│   ├── tools/           # Tool system (native + agent tools)
│   ├── skills/          # Skills system
│   ├── prompts/         # Sectional prompt system
│   ├── persistence/     # SQLite persistence
│   ├── api/             # FastAPI HTTP server
│   └── config/          # TOML config loading
└── open_agent/          # Multi-agent event-driven framework (worktree)
    ├── cli/             # Open-agent CLI
    ├── core/            # Session, orchestration, delegation
    ├── agents/          # Specialized agents (orchestrator, explorer, etc.)
    ├── bus/             # Event bus system
    ├── providers/       # LLM providers
    ├── tools/           # Tool registry
    ├── persistence/     # Storage layer
    └── config/          # Settings (uses .mini-agent/)

~/.mini-agent/           # Global config directory
└── config.toml          # Unified config for both agents

./.mini-agent/           # Project-local config (optional)
└── config.toml          # Overrides global config
```

## Configuration File Reference

### Provider Section
```toml
[provider]
name = "openai"                    # "openai", "openrouter", "ollama", or custom
model = "gpt-4o"                   # Model identifier
base_url = "..."                   # Optional: custom API endpoint
api_key = "sk-..."                 # Optional: or use env var
max_tokens = 4096                  # Max output tokens
temperature = 0.0                  # Sampling temperature
```

### Open-Agent Section
```toml
[open_agent]
default_agent = "orchestrator"     # Default agent role
max_delegation_depth = 3           # Max delegation nesting

[open_agent.background]
max_concurrent = 3                 # Max parallel background tasks

[open_agent.agents.orchestrator]   # Per-agent settings
model = "gpt-4o"
temperature = 0.0
allowed_tools = ["delegate_task", "read_file"]
can_delegate_to = ["explorer", "fixer"]
```

### Tool Approval Section
```toml
[tool_approval]
read_file = "auto_approve"
search_files = "auto_approve"
list_files = "auto_approve"
write_file = "always_ask"
edit_file = "always_ask"
execute_command = "always_ask"
attempt_completion = "auto_approve"
"*" = "ask_once"                   # Default policy
```

## Web UI

```bash
# Terminal 1: Start the backend API server
mini-agent serve --port 8080

# Terminal 2: Start the frontend dev server
cd ui/
npm install && npm run dev
# Opens http://localhost:5173
```

See [ui/README.md](ui/README.md) for full web UI documentation.

## HTTP API

Start the server:
```bash
mini-agent serve --port 8080
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/send` | Send message |
| GET | `/api/stream` | SSE event stream |
| POST | `/api/approvals/{id}` | Resolve tool approval |
| POST | `/api/inputs/{id}` | Resolve user input |

### Example

```bash
# Send a message
curl -X POST http://localhost:8080/api/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Explore the codebase", "agent_role": "explorer"}'

# Stream events
curl http://localhost:8080/api/stream
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_bus.py -v

# Run E2E tests (requires API key)
pytest tests/test_e2e_provider.py -v

# Run with coverage
pytest --cov=open_agent --cov-report=html
```

### Test Structure

| File | Description |
|------|-------------|
| `test_bus.py` | Event bus pub/sub |
| `test_delegation.py` | Agent delegation |
| `test_permissions.py` | Tool permissions |
| `test_persistence.py` | SQLite storage |
| `test_tools_native.py` | File ops, search, commands |
| `test_e2e_cli.py` | CLI E2E tests |
| `test_e2e_http.py` | HTTP API E2E tests |
| `test_e2e_provider.py` | LLM provider E2E |

## Development

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,api]"

# Lint & format
ruff check src --fix
ruff format src

# Run tests
pytest -x
```

## Worktrees

This repository uses git worktrees for parallel development:

- **main** — Main development branch (roo-agent + unified CLI)
- **open-agent** — Multi-agent framework worktree
- **coexistence-worktree** — Integration testing worktree

```bash
# List worktrees
git worktree list

# Add new worktree
git worktree add ../my-feature-branch feature-branch-name
```

## License

(To be determined)
