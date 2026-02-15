import { useCallback, useEffect } from 'react'
import { apiClient } from '../../lib/api/client'
import { useUIStore } from '../../lib/store/ui'
import { AlertIcon, CheckIcon, TerminalIcon } from '../icons'

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card rounded-xl shadow-2xl border border-border w-full max-w-lg mx-4 animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border bg-amber-400/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-400/10 flex items-center justify-center">
              <AlertIcon size={20} className="text-amber-400" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-foreground">Tool Approval Required</h2>
              <p className="text-sm text-muted-foreground">
                The agent wants to run <span className="font-mono font-medium text-foreground">{approval.tool_name}</span>
              </p>
            </div>
          </div>
        </div>

        {/* Parameters */}
        <div className="px-5 py-4 max-h-[300px] overflow-y-auto">
          <div className="flex items-center gap-2 mb-2">
            <TerminalIcon size={14} className="text-muted-foreground" />
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Parameters</h3>
          </div>
          <pre className="bg-muted/50 rounded-lg p-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap border border-border">
            {JSON.stringify(approval.params, null, 2)}
          </pre>
        </div>

        {/* Actions */}
        <div className="px-5 py-4 border-t border-border flex gap-2 justify-end bg-muted/30">
          <button
            onClick={() => handleDecision('n')}
            className="rounded-lg px-4 py-2 text-sm font-medium border border-border
                       hover:bg-destructive hover:text-destructive-foreground hover:border-destructive
                       transition-colors"
          >
            Deny <span className="text-muted-foreground text-xs ml-1">(N)</span>
          </button>
          <button
            onClick={() => handleDecision('y')}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-primary text-primary-foreground
                       hover:bg-primary/90 transition-colors flex items-center gap-1.5"
          >
            <CheckIcon size={14} />
            Allow Once <span className="text-primary-foreground/70 text-xs">(Y)</span>
          </button>
          <button
            onClick={() => handleDecision('always')}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-secondary text-secondary-foreground
                       hover:bg-secondary/80 transition-colors"
          >
            Always <span className="text-secondary-foreground/70 text-xs">(A)</span>
          </button>
        </div>
      </div>
    </div>
  )
}
