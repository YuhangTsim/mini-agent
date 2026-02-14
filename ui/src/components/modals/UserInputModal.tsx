import { useState, useCallback } from 'react'
import { apiClient } from '../../lib/api/client'
import { useUIStore } from '../../lib/store/ui'

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-background rounded-lg shadow-xl border border-border w-full max-w-lg mx-4">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold">Agent Needs Input</h2>
          <p className="text-sm text-foreground mt-2">{inputRequest.question}</p>
        </div>

        {/* Suggestions */}
        <div className="px-6 py-4 space-y-2">
          {inputRequest.suggestions.map((suggestion, i) => (
            <button
              key={i}
              onClick={() => handleSubmit(suggestion)}
              className="w-full text-left rounded-md px-4 py-3 text-sm border border-border
                         hover:bg-muted transition-colors"
            >
              <span className="font-medium text-primary mr-2">{i + 1}.</span>
              {suggestion}
            </button>
          ))}

          {/* Free text input */}
          <div className="flex gap-2 mt-3">
            <input
              type="text"
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && freeText.trim()) handleSubmit(freeText.trim())
              }}
              placeholder="Type your own response..."
              className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              onClick={() => freeText.trim() && handleSubmit(freeText.trim())}
              disabled={!freeText.trim()}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground
                         hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
