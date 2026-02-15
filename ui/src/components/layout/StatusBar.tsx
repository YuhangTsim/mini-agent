import { useAgentStore } from '../../lib/store/agent'
import { useUIStore } from '../../lib/store/ui'
import { ActivityIcon, SettingsIcon, CpuIcon, LoaderIcon } from '../icons'

export function StatusBar() {
  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const tasks = useAgentStore((s) => s.tasks)
  const isStreaming = useAgentStore((s) => s.isStreaming)
  const lastTokenUsage = useAgentStore((s) => s.lastTokenUsage)
  const setModal = useUIStore((s) => s.setModal)

  const currentTask = currentTaskId ? tasks.get(currentTaskId) : null

  return (
    <footer className="border-t border-border px-4 py-2 flex items-center justify-between text-xs bg-card shrink-0">
      <div className="flex items-center gap-4">
        {currentTask && (
          <>
            <button
              onClick={() => setModal('mode')}
              className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
            >
              <SettingsIcon size={12} />
              <span className="font-medium">{currentTask.mode}</span>
            </button>
            
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <ActivityIcon size={12} />
              <span className="capitalize">{currentTask.status}</span>
            </div>
          </>
        )}
        
        {isStreaming && (
          <div className="flex items-center gap-1.5 text-primary">
            <LoaderIcon size={12} className="animate-spin" />
            <span className="animate-pulse">Thinking...</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-4">
        {currentTask && (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <CpuIcon size={12} />
            <span>
              {(currentTask.token_usage.input_tokens + currentTask.token_usage.output_tokens).toLocaleString()} tokens
            </span>
          </div>
        )}
        {lastTokenUsage && (
          <span className="text-muted-foreground/70">
            +{(lastTokenUsage.input_tokens + lastTokenUsage.output_tokens).toLocaleString()}
          </span>
        )}
      </div>
    </footer>
  )
}
