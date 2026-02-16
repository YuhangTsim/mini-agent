# Open-Agent

A multi-agent AI framework with typed event bus and hierarchical delegation.

## Overview

Open-Agent replaces single-mode agents with multiple specialized agents, each running their own session with independent LLM configuration and tool access. The orchestrator agent delegates tasks to specialist agents (explorer, librarian, oracle, designer, fixer) based on the work required.

## Features

- **6 Specialized Agents**: orchestrator, explorer, librarian, oracle, designer, fixer
- **Typed Event Bus**: Async pub/sub with queue streams for real-time updates
- **Hierarchical Delegation**: Orchestrator delegates to specialists with depth limiting
- **Permission System**: Fine-grained tool access control per agent
- **Background Tasks**: Fire-and-forget with semaphore-controlled concurrency
- **Hook System**: Extensible before/after tool hooks
- **SQLite Persistence**: Async storage for sessions, messages, and tool calls
- **Streaming CLI**: Rich terminal UI with live markdown rendering
- **HTTP API**: FastAPI server with SSE streaming

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd minimal-agent/main

# Create virtual environment and install
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# For HTTP API support
uv pip install -e ".[dev,api]"
```

## Quick Start

```bash
# Set your API key
export OPENAI_API_KEY="sk-..."

# Run the CLI
open-agent

# Or start the HTTP API server
open-agent serve --port 8080
```

## Architecture

```
src/open_agent/
├── agents/          # Agent implementations
│   ├── orchestrator.py   # Delegates to specialists
│   ├── explorer.py       # File exploration
│   ├── librarian.py      # Documentation research
│   ├── oracle.py         # Architecture decisions
│   ├── designer.py       # UI/UX design
│   └── fixer.py          # Implementation
├── bus/             # Typed async EventBus
├── core/            # Session & delegation
├── tools/           # Native tools & permissions
├── providers/       # LLM provider abstraction
├── persistence/     # SQLite storage
├── prompts/         # Prompt composition
├── api/             # HTTP API & service
└── cli/             # Interactive REPL
```

## Available Agents

| Agent | Purpose | Can Delegate To |
|-------|---------|-----------------|
| **orchestrator** | Task analysis and delegation | All specialists |
| **explorer** | File/code exploration | — |
| **librarian** | Documentation & research | — |
| **oracle** | Architecture decisions | explorer |
| **designer** | UI/UX design | — |
| **fixer** | Implementation & debugging | — |

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
ruff check . --fix
ruff format .

# Type checking
mypy src/open_agent

# Run tests
pytest -x
```

## Project Structure

```
.
├── src/open_agent/     # Source code
├── tests/              # Test suite
├── pyproject.toml      # Dependencies & config
└── .open-agent/        # Local config & data
```

## License

(To be determined)
