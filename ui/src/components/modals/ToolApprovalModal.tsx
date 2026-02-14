import { useCallback, useEffect } from 'react'
import { apiClient } from '../../lib/api/client'
import { useUIStore } from '../../lib/store/ui'

export function ToolApprovalModal() {
  const currentModal = useUIStore((s) => s.currentModal)
  const approval = useUIStore((s) => s.currentApproval())
  const removeApproval = useUIStore((s) => s.removeApproval)

  const handleDecision = useCallback(
    async (decision: 'y' | 'n' | 'always') => {
      if (!approval) return
      try {
        await apiClient.respondToApproval(approval.approval_id, decision)
      } catch (err) {
        console.error('Failed to send approval:', err)
      }
      removeApproval(approval.approval_id)
    },
    [approval, removeApproval]
  )

  // Keyboard shortcuts
  useEffect(() => {
    if (currentModal !== 'approval' || !approval) return

    const handler = (e: KeyboardEvent) => {
      if (e.key === 'y' || e.key === 'Y') handleDecision('y')
      else if (e.key === 'n' || e.key === 'N') handleDecision('n')
      else if (e.key === 'a' || e.key === 'A') handleDecision('always')
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [currentModal, approval, handleDecision])

  if (currentModal !== 'approval' || !approval) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-xl border border-border w-full max-w-lg mx-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">Tool Approval Required</h2>
          <p className="text-sm text-muted-foreground mt-1">
            The agent wants to use <span className="font-mono font-medium text-foreground">{approval.tool_name}</span>
          </p>
        </div>

        {/* Parameters */}
        <div className="px-6 py-4 max-h-[300px] overflow-y-auto">
          <h3 className="text-sm font-medium text-muted-foreground mb-2">Parameters:</h3>
          <pre className="bg-muted rounded-lg p-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(approval.params, null, 2)}
          </pre>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-border flex gap-2 justify-end">
          <button
            onClick={() => handleDecision('n')}
            className="rounded-md px-4 py-2 text-sm font-medium border border-border
                       hover:bg-destructive hover:text-destructive-foreground transition-colors"
          >
            Deny (N)
          </button>
          <button
            onClick={() => handleDecision('y')}
            className="rounded-md px-4 py-2 text-sm font-medium bg-primary text-primary-foreground
                       hover:bg-primary/90 transition-colors"
          >
            Allow Once (Y)
          </button>
          <button
            onClick={() => handleDecision('always')}
            className="rounded-md px-4 py-2 text-sm font-medium bg-secondary text-secondary-foreground
                       hover:bg-secondary/80 transition-colors"
          >
            Always Allow (A)
          </button>
        </div>
      </div>
    </div>
  )
}
