import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../../lib/api/client'
import { useAgentStore } from '../../lib/store/agent'
import { useUIStore } from '../../lib/store/ui'
import type { Mode } from '../../lib/api/types'

export function ModeSelector() {
  const currentModal = useUIStore((s) => s.currentModal)
  const setModal = useUIStore((s) => s.setModal)
  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const tasks = useAgentStore((s) => s.tasks)
  const updateTask = useAgentStore((s) => s.updateTask)
  const [modes, setModes] = useState<Mode[]>([])

  const currentTask = currentTaskId ? tasks.get(currentTaskId) : null

  useEffect(() => {
    if (currentModal === 'mode') {
      apiClient.listModes().then((res) => setModes(res.modes)).catch(console.error)
    }
  }, [currentModal])

  const handleSelectMode = useCallback(
    async (modeSlug: string) => {
      if (!currentTaskId) return
      try {
        const updatedTask = await apiClient.switchMode(currentTaskId, modeSlug)
        updateTask(updatedTask)
      } catch (err) {
        console.error('Failed to switch mode:', err)
      }
      setModal(null)
    },
    [currentTaskId, updateTask, setModal]
  )

  if (currentModal !== 'mode') return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-xl border border-border w-full max-w-md mx-4">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h2 className="text-lg font-semibold">Switch Mode</h2>
          <button
            onClick={() => setModal(null)}
            className="text-muted-foreground hover:text-foreground"
          >
            x
          </button>
        </div>

        <div className="p-4 space-y-2">
          {modes.map((mode) => (
            <button
              key={mode.slug}
              onClick={() => handleSelectMode(mode.slug)}
              className={`w-full text-left rounded-lg px-4 py-3 border transition-colors ${
                currentTask?.mode === mode.slug
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:bg-muted'
              }`}
            >
              <div className="font-medium">
                {mode.name}
                {currentTask?.mode === mode.slug && (
                  <span className="ml-2 text-xs text-primary">(current)</span>
                )}
              </div>
              <div className="text-xs text-muted-foreground mt-1">{mode.when_to_use}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
