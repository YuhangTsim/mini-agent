# Mini-Agent

A modular, controllable AI agent framework in Python. Provider-agnostic (starting with OpenAI), with task hierarchies, full persistence, and a clean API layer decoupled from any frontend.

## Quick Start

```bash
# Install with uv
uv venv && uv pip install -e ".[dev]"

# Set your API key
export OPENAI_API_KEY="sk-..."

# Run the interactive REPL
mini-agent
```

## Features

- **Multi-mode system** — code, plan, ask, debug, orchestrator modes with per-mode tool access
- **11 built-in tools** — file ops, search, command execution, todo lists, user interaction, task management
- **Task hierarchy** — parent/child tasks with independent conversations and result propagation
- **Full persistence** — SQLite-backed storage for tasks, messages, and tool call audit logs
- **Skills system** — Markdown skill files with YAML frontmatter, mode-scoped, auto-discovered
- **Configurable approval** — per-tool approval policies (auto_approve, always_ask, ask_once, deny)
- **Streaming responses** — real-time token streaming with rich terminal formatting
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
│   └── events.py        # Event bus for real-time updates
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

## License

(To be determined)
