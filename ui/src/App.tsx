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
import { BotIcon, PlusIcon, LoaderIcon, AlertIcon, MessageSquareIcon, SparklesIcon } from './components/icons'
import type { HealthResponse, Mode } from './lib/api/types'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [modes, setModes] = useState<Mode[]>([])
  const [selectedMode, setSelectedMode] = useState('code')
  const [taskTitle, setTaskTitle] = useState('')
  const [isCreating, setIsCreating] = useState(false)

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
    if (isCreating) return
    setIsCreating(true)
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
    } finally {
      setIsCreating(false)
    }
  }, [taskTitle, selectedMode, addTask, setCurrentTask, isCreating])

  // Show connection screen before API is ready
  if (!health) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <div className="text-center space-y-6 px-4">
          <div className="flex items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <BotIcon size={28} className="text-primary" />
            </div>
            <h1 className="text-4xl font-bold">Mini-Agent</h1>
          </div>
          {error ? (
            <div className="p-5 rounded-xl bg-red-400/10 border border-red-400/20 text-red-400 max-w-md">
              <div className="flex items-center gap-2 mb-2">
                <AlertIcon size={18} />
                <span className="font-semibold">Connection Error</span>
              </div>
              <p className="text-sm mb-3">{error}</p>
              <p className="text-xs text-red-400/80">
                Make sure the backend is running:
              </p>
              <code className="mt-2 block bg-red-400/10 px-3 py-2 rounded text-xs font-mono">
                mini-agent serve --port 8080
              </code>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <LoaderIcon size={24} className="text-primary animate-spin" />
              <p className="text-muted-foreground">Connecting to API...</p>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      <header className="border-b border-border px-4 py-3 flex items-center justify-between shrink-0 bg-card">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <BotIcon size={18} className="text-primary" />
          </div>
          <h1 className="text-lg font-bold">Mini-Agent</h1>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            v{health.version}
          </span>
        </div>

        {currentTask && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground font-mono text-xs bg-muted px-2 py-0.5 rounded">
              {currentTaskId!.slice(0, 8)}
            </span>
            <button
              onClick={() => setModal('mode')}
              className="flex items-center gap-1.5 text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full 
                         hover:bg-primary/20 transition-colors font-medium"
            >
              <SparklesIcon size={12} />
              {currentTask.mode}
            </button>
          </div>
        )}
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-72 border-r border-border flex flex-col shrink-0 bg-card">
          {/* New task form */}
          <div className="p-3 space-y-2 border-b border-border">
            <input
              type="text"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateTask()}
              placeholder="Task title..."
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                         placeholder:text-muted-foreground/60 transition-all"
            />
            <div className="flex gap-2">
              <select
                value={selectedMode}
                onChange={(e) => setSelectedMode(e.target.value)}
                className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-xs
                           focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                           cursor-pointer transition-all"
              >
                {modes.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name}
                  </option>
                ))}
              </select>
              <button
                onClick={handleCreateTask}
                disabled={isCreating}
                className="rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground
                           hover:bg-primary/90 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed
                           transition-all flex items-center gap-1.5"
              >
                {isCreating ? (
                  <LoaderIcon size={14} className="animate-spin" />
                ) : (
                  <PlusIcon size={14} />
                )}
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
                  className={`w-full text-left rounded-lg px-3 py-2.5 text-sm transition-all duration-200 group ${
                    currentTaskId === task.id
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'hover:bg-muted text-foreground border border-transparent'
                  }`}
                >
                  <div className="font-medium truncate flex items-center gap-2">
                    {currentTaskId === task.id && (
                      <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    )}
                    {task.title}
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center gap-2 mt-1">
                    <span className="px-1.5 py-0.5 rounded bg-muted">{task.mode}</span>
                    <span className="capitalize">{task.status}</span>
                  </div>
                </button>
              ))}

            {tasks.size === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <MessageSquareIcon size={24} className="mb-2 opacity-50" />
                <p className="text-xs">No tasks yet</p>
                <p className="text-[10px] opacity-60">Create one above</p>
              </div>
            )}
          </div>

          {/* Todo panel at bottom of sidebar */}
          {currentTask && currentTask.todo_list.length > 0 && (
            <TodoPanel items={currentTask.todo_list} />
          )}
        </aside>

        {/* Chat area */}
        <main className="flex-1 flex flex-col overflow-hidden bg-background">
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
