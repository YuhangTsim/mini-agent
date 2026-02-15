# Coexistence Architecture - Worktree

**Branch:** `feature/coexistence-architecture`
**Status:** Sprint 1 Complete (Rename & Restructure)

## Changes Made

### 1. Renamed mini_agent → roo_agent
- Directory: `src/mini_agent/` → `src/roo_agent/`
- Updated all imports in tests
- Updated CLI branding and messages
- Updated `pyproject.toml` package configuration

### 2. Merged open-agent
- Copied `open-agent/src/open_agent/` → `src/open_agent/`
- Updated `pyproject.toml` to include both packages
- Added CLI entry point for open-agent

### 3. Created Unified Package
- New: `src/minimal_agent/` - unified entry point
- Lazy imports: `from minimal_agent import roo, open`
- Unified CLI with `--open` flag to select framework

### 4. Updated Configuration
- Package name: `minimal-agent` v2.0.0
- CLI commands:
  - `mini-agent` - **Main entry point, defaults to roo-agent**
  - `mini-agent --open` - Use open-agent instead
  - `roo-agent` - Direct roo-agent access
  - `open-agent` - Direct open-agent access

## Directory Structure

```
src/
├── roo_agent/          # Formerly mini_agent (mode-based)
│   ├── core/
│   ├── cli/
│   ├── api/
│   └── ...
├── open_agent/         # Multi-agent framework
│   ├── core/
│   ├── agents/
│   ├── bus/
│   └── ...
└── minimal_agent/      # Unified entry point
    ├── __init__.py
    └── cli.py
```

## Usage

### CLI (Recommended)

```bash
# Install the package
uv pip install -e .

# Default: roo-agent (mode-based)
mini-agent

# Use open-agent (multi-agent event-driven)
mini-agent --open

# Direct access (bypass main CLI)
roo-agent
open-agent
```

### Python API

```python
from minimal_agent import roo, open

# Roo-agent (mode-based) - DEFAULT
agent = roo.Agent(mode="coder")

# Open-agent (multi-agent)
session = open.Session()
orchestrator = open.Orchestrator(session)
```

## Testing

Both frameworks are independent and can be tested separately:

```bash
# Test roo-agent
uv run pytest tests/ -k roo

# Test open-agent (needs test suite in open_agent/tests/)
uv run pytest src/open_agent/tests/
```

## Framework Comparison

| | Roo-Agent (Default) | Open-Agent |
|---|---------------------|------------|
| **Paradigm** | Single agent with switchable modes | Multiple specialized agents |
| **Architecture** | Mode-based (Roo Code style) | Event-driven with event bus |
| **Best for** | Focused tasks, code editing | Complex multi-domain workflows |
| **CLI** | `mini-agent` (default) | `mini-agent --open` |

## Next Steps

### Sprint 2: Shared Infrastructure
- [ ] Create `frameworks/shared/` with common utilities
- [ ] Abstract base classes for agents and tools
- [ ] Shared LLM clients, memory, tool registry

### Sprint 3: Unified Skills
- [ ] Skill adapter pattern
- [ ] Unified skill directory
- [ ] Framework-specific adapters

### Sprint 4: UI Refactoring
- [ ] Framework selector in UI
- [ ] Roo-specific and Open-specific components

### Sprint 5: Documentation
- [x] Updated README with dual framework usage
- [ ] Migration guide from mini-agent
- [ ] API documentation

## Notes

- `mini-agent` is now the main entry point and defaults to roo-agent
- Use `--open` flag to switch to open-agent
- Original `mini-agent` behavior preserved (runs roo-agent by default)
- `open-agent` worktree remains in main repo, but code is now in `src/open_agent/`
- Both frameworks share the same Python environment
- Database schemas are separate (roo uses SQLite, open has its own persistence)
