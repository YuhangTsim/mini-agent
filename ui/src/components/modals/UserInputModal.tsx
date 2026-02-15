import { useState, useCallback } from 'react'
import { apiClient } from '../../lib/api/client'
import { useUIStore } from '../../lib/store/ui'
import { MessageSquareIcon, SendIcon } from '../icons'

export function UserInputModal() {
  const currentModal = useUIStore((s) => s.currentModal)
  const inputRequest = useUIStore((s) => s.inputRequest)
  const setInputRequest = useUIStore((s) => s.setInputRequest)
  const [freeText, setFreeText] = useState('')

  const handleSubmit = useCallback(
    async (answer: string) => {
      if (!inputRequest) return
      try {
        await apiClient.respondToInput(inputRequest.input_id, answer)
      } catch (err) {
        console.error('Failed to send input:', err)
      }
      setInputRequest(null)
      setFreeText('')
    },
    [inputRequest, setInputRequest]
  )

  if (currentModal !== 'input' || !inputRequest) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card rounded-xl shadow-2xl border border-border w-full max-w-lg mx-4 animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border bg-primary/5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <MessageSquareIcon size={20} className="text-primary" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-foreground">Agent Needs Input</h2>
              <p className="text-sm text-muted-foreground">Please provide more information</p>
            </div>
          </div>
        </div>

        {/* Question */}
        <div className="px-5 py-4">
          <p className="text-foreground leading-relaxed">{inputRequest.question}</p>
        </div>

        {/* Suggestions */}
        <div className="px-5 pb-2 space-y-2">
          {inputRequest.suggestions.map((suggestion, i) => (
            <button
              key={i}
              onClick={() => handleSubmit(suggestion)}
              className="w-full text-left rounded-lg px-4 py-3 text-sm border border-border
                         hover:border-primary/50 hover:bg-primary/5 transition-all duration-200
                         flex items-center gap-3 group"
            >
              <span className="flex items-center justify-center w-6 h-6 rounded-md bg-muted text-muted-foreground text-xs font-medium group-hover:bg-primary/20 group-hover:text-primary transition-colors">
                {i + 1}
              </span>
              <span className="text-foreground">{suggestion}</span>
            </button>
          ))}

          {/* Free text input */}
          <div className="flex gap-2 mt-4 pt-3 border-t border-border">
            <input
              type="text"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && freeText.trim()) handleSubmit(freeText.trim())
              }}
              placeholder="Or type your own response..."
              className="flex-1 rounded-lg border border-input bg-background px-4 py-2.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                         placeholder:text-muted-foreground/60 transition-all"
            />
            <button
              onClick={() => freeText.trim() && handleSubmit(freeText.trim())}
              disabled={!freeText.trim()}
              className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground
                         hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all flex items-center gap-2"
            >
              <SendIcon size={14} />
              <span>Send</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
