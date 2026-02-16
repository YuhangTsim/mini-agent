# Open-Agent

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

| Agent | Purpose | Can Delegate To |
|-------|---------|-----------------|
| **orchestrator** | Task analysis and delegation | All specialists |
| **explorer** | File/code exploration | — |
| **librarian** | Documentation & research | — |
| **oracle** | Architecture decisions | explorer |
| **designer** | UI/UX design | — |
| **fixer** | Implementation & debugging | — |

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

Create `.open-agent/config.toml`:

```toml
[provider]
name = "openai"
model = "gpt-4o"
base_url = "https://api.openai.com/v1"  # Optional

[agents.orchestrator]
model = "gpt-4o"
temperature = 0.0

[agents.explorer]
model = "gpt-4o-mini"

[[permissions]]
tool = "execute_command"
action = "ask"

[[permissions]]
tool = "write_file"
pattern = "*.py"
action = "ask"
```

### Providers

Supports any OpenAI-compatible API:

**OpenAI (default)**:
```toml
[provider]
name = "openai"
model = "gpt-4o"
```

**OpenRouter**:
```toml
[provider]
name = "openrouter"
model = "anthropic/claude-sonnet-4"
base_url = "https://openrouter.ai/api/v1"
```

**Ollama (local)**:
```toml
[provider]
name = "ollama"
model = "llama3"
base_url = "http://localhost:11434/v1"
```

## CLI Usage

```bash
# Start interactive session
open-agent

# List available agents
open-agent agents

# Start with specific agent
open-agent --agent explorer

# Start API server
open-agent serve --port 8080
```

### Interactive Commands

| Command | Description |
|---------|-------------|
| `@agent <name>` | Switch to agent |
| `/agents` | List available agents |
| `/history` | Show conversation history |
| `/quit` | Exit |

## HTTP API

Start the server:
```bash
open-agent serve --port 8080
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
ruff check src/open_agent tests --fix
ruff format src/open_agent tests

# Run tests
pytest -x
```

## Project Structure

```
.
├── src/
│   ├── open_agent/     # Active framework (installed)
│   └── mini_agent/     # Legacy (not installed)
├── tests/              # Test suite (open_agent)
├── pyproject.toml      # Dependencies & config
└── .open-agent/        # Local config & data
```

## License

(To be determined)
