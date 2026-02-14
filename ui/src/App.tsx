import { useState, useEffect, useCallback } from 'react'
import { apiClient } from './lib/api/client'
import { useAgentStore } from './lib/store/agent'
import { useUIStore } from './lib/store/ui'
import { ChatPanel } from './components/chat/ChatPanel'
import { TodoPanel } from './components/todo/TodoPanel'
import { StatusBar } from './components/layout/StatusBar'
import { ToolApprovalModal } from './components/modals/ToolApprovalModal'
import { UserInputModal } from './components/modals/UserInputModal'
import { ModeSelector } from './components/modals/ModeSelector'
import type { HealthResponse, Mode } from './lib/api/types'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [modes, setModes] = useState<Mode[]>([])
  const [selectedMode, setSelectedMode] = useState('code')
  const [taskTitle, setTaskTitle] = useState('')

  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const setCurrentTask = useAgentStore((s) => s.setCurrentTask)
  const addTask = useAgentStore((s) => s.addTask)
  const tasks = useAgentStore((s) => s.tasks)
  const setModal = useUIStore((s) => s.setModal)

  const currentTask = currentTaskId ? tasks.get(currentTaskId) : null

  useEffect(() => {
    apiClient
      .health()
      .then(setHealth)
      .catch((err) => setError(err.message))

    apiClient
      .listModes()
      .then((res) => setModes(res.modes))
      .catch(console.error)
  }, [])

  const handleCreateTask = useCallback(async () => {
    try {
      const title = taskTitle.trim() || 'New Task'
      const task = await apiClient.createTask({
        description: title,
        mode: selectedMode,
        title,
      })
      addTask(task)
      setCurrentTask(task.id)
      setTaskTitle('')
    } catch (err: unknown) {
      console.error('Failed to create task:', err)
    }
  }, [taskTitle, selectedMode, addTask, setCurrentTask])

  // Show connection screen before API is ready
  if (!health) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold">Mini-Agent</h1>
          {error ? (
            <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300">
              API Error: {error}
              <p className="text-sm mt-2">
                Make sure the backend is running:{' '}
                <code className="bg-red-100 dark:bg-red-900/40 px-1 rounded">
                  mini-agent serve --port 8080
                </code>
              </p>
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-muted text-muted-foreground">
              Connecting to API...
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      <header className="border-b border-border px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold">Mini-Agent</h1>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
            v{health.version}
          </span>
        </div>

        {currentTask && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground font-mono text-xs">
              {currentTaskId!.slice(0, 8)}
            </span>
            <button
              onClick={() => setModal('mode')}
              className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded hover:bg-primary/20 transition-colors"
            >
              {currentTask.mode}
            </button>
          </div>
        )}
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 border-r border-border flex flex-col shrink-0">
          {/* New task form */}
          <div className="p-3 space-y-2 border-b border-border">
            <input
              type="text"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateTask()}
              placeholder="Task title..."
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="flex gap-2">
              <select
                value={selectedMode}
                onChange={(e) => setSelectedMode(e.target.value)}
                className="flex-1 rounded-md border border-input bg-background px-2 py-1.5 text-xs
                           focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {modes.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name}
                  </option>
                ))}
              </select>
              <button
                onClick={handleCreateTask}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground
                           hover:bg-primary/90 transition-colors"
              >
                New
              </button>
            </div>
          </div>

          {/* Task list */}
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {Array.from(tasks.values())
              .reverse()
              .map((task) => (
                <button
                  key={task.id}
                  onClick={() => setCurrentTask(task.id)}
                  className={`w-full text-left rounded-md px-3 py-2 text-sm transition-colors ${
                    currentTaskId === task.id
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-muted text-foreground'
                  }`}
                >
                  <div className="font-medium truncate">{task.title}</div>
                  <div className="text-xs text-muted-foreground flex items-center gap-1">
                    <span>{task.mode}</span>
                    <span>·</span>
                    <span>{task.status}</span>
                  </div>
                </button>
              ))}

            {tasks.size === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                No tasks yet. Create one above.
              </p>
            )}
          </div>

          {/* Todo panel at bottom of sidebar */}
          {currentTask && currentTask.todo_list.length > 0 && (
            <TodoPanel items={currentTask.todo_list} />
          )}
        </aside>

        {/* Chat area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <ChatPanel />
        </main>
      </div>

      {/* Status bar */}
      <StatusBar />

      {/* Modals */}
      <ToolApprovalModal />
      <UserInputModal />
      <ModeSelector />
    </div>
  )
}

export default App
