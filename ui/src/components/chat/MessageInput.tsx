import { useState, type KeyboardEvent } from 'react'
import { SendIcon } from '../icons'

interface MessageInputProps {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function MessageInput({ onSend, disabled, placeholder }: MessageInputProps) {
  const [input, setInput] = useState('')

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-border p-4 bg-card">
      <div className="flex gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "Type a message... (Enter to send, Shift+Enter for newline)"}
            disabled={disabled}
            rows={1}
            className="w-full resize-none rounded-xl border border-input bg-background px-4 py-3 pr-12 text-sm
                       focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                       disabled:opacity-50 disabled:cursor-not-allowed
                       min-h-[48px] max-h-[200px] placeholder:text-muted-foreground/60 transition-all"
            style={{ fieldSizing: 'content' } as React.CSSProperties}
          />
          {/* Character count / hint */}
          <div className="absolute bottom-2 right-3 text-xs text-muted-foreground/50 pointer-events-none">
            {input.length > 0 && `${input.length}`}
          </div>
        </div>
        <button
          onClick={handleSend}
          disabled={disabled || !input.trim()}
          className="rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground
                     hover:bg-primary/90 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
                     transition-all duration-200 flex items-center gap-2 shadow-lg shadow-primary/20"
        >
          <SendIcon size={16} />
          <span className="hidden sm:inline">Send</span>
        </button>
      </div>
    </div>
  )
}
