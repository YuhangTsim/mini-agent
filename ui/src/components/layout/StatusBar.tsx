import { useAgentStore } from '../../lib/store/agent'
import { useUIStore } from '../../lib/store/ui'

export function StatusBar() {
  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const tasks = useAgentStore((s) => s.tasks)
  const isStreaming = useAgentStore((s) => s.isStreaming)
  const lastTokenUsage = useAgentStore((s) => s.lastTokenUsage)
  const setModal = useUIStore((s) => s.setModal)

  const currentTask = currentTaskId ? tasks.get(currentTaskId) : null

  return (
    <footer className="border-t border-border px-4 py-1.5 flex items-center justify-between text-xs text-muted-foreground shrink-0">
      <div className="flex items-center gap-3">
        {currentTask && (
          <>
            <button
              onClick={() => setModal('mode')}
              className="hover:text-foreground transition-colors"
            >
              Mode: <span className="font-medium">{currentTask.mode}</span>
            </button>
            <span>|</span>
            <span>Status: {currentTask.status}</span>
          </>
        )}
        {isStreaming && (
          <>
            <span>|</span>
            <span className="text-primary animate-pulse">Streaming...</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {currentTask && (
          <span>
            Tokens: {(currentTask.token_usage.input_tokens + currentTask.token_usage.output_tokens).toLocaleString()}
          </span>
        )}
        {lastTokenUsage && (
          <span>
            (last: {lastTokenUsage.input_tokens.toLocaleString()} in / {lastTokenUsage.output_tokens.toLocaleString()} out)
          </span>
        )}
      </div>
    </footer>
  )
}
