import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../../lib/api/client'
import { useAgentStore } from '../../lib/store/agent'
import { useUIStore } from '../../lib/store/ui'
import { SettingsIcon, XIcon, CheckIcon } from '../icons'
import type { Mode } from '../../lib/api/types'

export function ModeSelector() {
  const currentModal = useUIStore((s) => s.currentModal)
  const setModal = useUIStore((s) => s.setModal)
  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const tasks = useAgentStore((s) => s.tasks)
  const updateTask = useAgentStore((s) => s.updateTask)
  const [modes, setModes] = useState<Mode[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const currentTask = currentTaskId ? tasks.get(currentTaskId) : null

  useEffect(() => {
    if (currentModal === 'mode') {
      apiClient.listModes().then((res) => setModes(res.modes)).catch(console.error)
    }
  }, [currentModal])

  const handleSelectMode = useCallback(
    async (modeSlug: string) => {
      if (!currentTaskId || modeSlug === currentTask?.mode) {
        setModal(null)
        return
      }
      setIsLoading(true)
      try {
        const updatedTask = await apiClient.switchMode(currentTaskId, modeSlug)
        updateTask(updatedTask)
      } catch (err) {
        console.error('Failed to switch mode:', err)
      } finally {
        setIsLoading(false)
        setModal(null)
      }
    },
    [currentTaskId, updateTask, setModal, currentTask?.mode]
  )

  if (currentModal !== 'mode') return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card rounded-xl shadow-2xl border border-border w-full max-w-md mx-4 animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2">
            <SettingsIcon size={18} className="text-primary" />
            <h2 className="text-base font-semibold text-foreground">Switch Mode</h2>
          </div>
          <button
            onClick={() => setModal(null)}
            className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg p-1.5 transition-colors"
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Mode list */}
        <div className="p-3 space-y-1 max-h-[400px] overflow-y-auto">
          {modes.map((mode) => {
            const isCurrent = currentTask?.mode === mode.slug
            return (
              <button
                key={mode.slug}
                onClick={() => handleSelectMode(mode.slug)}
                disabled={isLoading}
                className={`w-full text-left rounded-lg px-4 py-3 border transition-all duration-200 group ${
                  isCurrent
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-primary/50 hover:bg-muted/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="font-medium text-foreground">
                    {mode.name}
                  </div>
                  {isCurrent && (
                    <span className="flex items-center gap-1 text-xs text-primary font-medium">
                      <CheckIcon size={12} />
                      Active
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  {mode.when_to_use}
                </div>
                {mode.tool_groups.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {mode.tool_groups.map((group) => (
                      <span 
                        key={group} 
                        className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                      >
                        {group}
                      </span>
                    ))}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
