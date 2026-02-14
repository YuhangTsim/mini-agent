# Mini-Agent Web UI

A web-based chat interface for Mini-Agent, providing streaming responses, tool approvals, task management, and mode switching.

## Prerequisites

- Node.js 18+
- Python 3.11+ with `uv`
- Mini-Agent backend with API dependencies installed

## Quick Start

### 1. Install backend API dependencies

```bash
cd main/
uv pip install -e ".[api]"
```

### 2. Install frontend dependencies

```bash
cd ui/
npm install
```

### 3. Run in development mode (two terminals)

```bash
# Terminal 1: Start the backend API server
cd main/
uv run mini-agent serve --port 8080

# Terminal 2: Start the frontend dev server (hot reload)
cd ui/
npm run dev
# Opens http://localhost:5173
```

The Vite dev server proxies `/api` requests to `localhost:8080` automatically.

### 4. Run in production mode (single server)

```bash
# Build the frontend
cd ui/
npm run build

# Serve everything from the backend
cd main/
uv run mini-agent serve --port 8080 --static-dir ../ui/dist

# Open http://localhost:8080
```

## Features

- **Chat interface** — Send messages, see streaming LLM responses with markdown rendering and syntax highlighting
- **Tool approvals** — Approve/deny tool execution with Allow Once, Always Allow, or Deny (keyboard shortcuts: Y/N/A)
- **Task management** — Create tasks, switch between them in the sidebar
- **Mode switching** — Switch between Code, Architect, Ask, Debug, and Orchestrator modes
- **Todo list** — View the agent's todo list progress in the sidebar
- **Status bar** — Current mode, task status, and token usage

## Project Structure

```
ui/
├── src/
│   ├── App.tsx                          # Root component (layout, sidebar, task creation)
│   ├── main.tsx                         # Entry point (React + QueryClient setup)
│   ├── index.css                        # Tailwind CSS theme
│   │
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx            # Main chat interface
│   │   │   ├── MessageList.tsx          # Scrolling message history
│   │   │   ├── MessageInput.tsx         # Text input with send button
│   │   │   ├── StreamingMessage.tsx     # Live LLM text with cursor
│   │   │   └── ToolCallDisplay.tsx      # Tool execution status
│   │   ├── modals/
│   │   │   ├── ToolApprovalModal.tsx    # Approve/deny tool execution
│   │   │   ├── UserInputModal.tsx       # Agent asking for user input
│   │   │   └── ModeSelector.tsx         # Switch between modes
│   │   ├── todo/
│   │   │   └── TodoPanel.tsx            # Todo list display
│   │   └── layout/
│   │       └── StatusBar.tsx            # Bottom status bar
│   │
│   ├── hooks/
│   │   └── useAgentStream.ts            # SSE event subscription hook
│   │
│   └── lib/
│       ├── api/
│       │   ├── client.ts                # HTTP client (fetch wrapper)
│       │   ├── sse.ts                   # SSE connection with reconnection
│       │   └── types.ts                 # TypeScript types (matches backend)
│       └── store/
│           ├── agent.ts                 # Zustand: messages, streaming, tasks
│           └── ui.ts                    # Zustand: modals, approval queue
│
├── vite.config.ts                       # Vite config with API proxy
├── tailwind.config.js                   # Tailwind theme (shadcn/ui compatible)
├── tsconfig.json                        # TypeScript config
└── package.json                         # Dependencies
```

## API Endpoints

The backend exposes these endpoints (all under `/api`):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/tasks` | Create a new task |
| GET | `/api/tasks` | List all tasks |
| GET | `/api/tasks/{id}` | Get task details |
| DELETE | `/api/tasks/{id}` | Cancel a task |
| POST | `/api/tasks/{id}/mode` | Switch task mode |
| POST | `/api/tasks/{id}/messages` | Send a message |
| GET | `/api/tasks/{id}/messages` | Get message history |
| GET | `/api/tasks/{id}/stream` | SSE event stream |
| POST | `/api/approvals/{id}` | Respond to tool approval |
| POST | `/api/inputs/{id}` | Respond to user input request |
| GET | `/api/modes` | List available modes |

## Tech Stack

- **React 19** + **TypeScript** + **Vite** — Frontend framework and build tool
- **Tailwind CSS v4** — Utility-first styling
- **Zustand** — Lightweight state management
- **TanStack Query** — Server state and caching
- **react-markdown** + **react-syntax-highlighter** — Markdown rendering with code highlighting
- **FastAPI** + **sse-starlette** — Backend HTTP API with Server-Sent Events

## Notes

- The web UI and CLI (TUI) are completely independent — they share the same `AgentService` layer but don't interfere with each other
- The CLI continues to work as before via `mini-agent` or `mini-agent chat`
- SSE connections include automatic reconnection with exponential backoff
- Tool approvals pause the agent loop until the user responds via the modal
