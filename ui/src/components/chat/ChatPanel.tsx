import { useCallback } from 'react'
import { apiClient } from '../../lib/api/client'
import { useAgentStore } from '../../lib/store/agent'
import { useAgentStream } from '../../hooks/useAgentStream'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { StreamingMessage } from './StreamingMessage'
import { ToolCallDisplay } from './ToolCallDisplay'

export function ChatPanel() {
  const currentTaskId = useAgentStore((s) => s.currentTaskId)
  const messages = useAgentStore((s) =>
    currentTaskId ? s.messages.get(currentTaskId) || [] : []
  )
  const streamingText = useAgentStore((s) => s.streamingText)
  const isStreaming = useAgentStore((s) => s.isStreaming)
  const activeToolCalls = useAgentStore((s) => s.activeToolCalls)
  const addMessage = useAgentStore((s) => s.addMessage)
  const clearToolCalls = useAgentStore((s) => s.clearToolCalls)
  const lastTokenUsage = useAgentStore((s) => s.lastTokenUsage)

  // Subscribe to SSE events for the current task
  useAgentStream(currentTaskId)

  const handleSend = useCallback(
    async (content: string) => {
      if (!currentTaskId) return

      // Add user message to the store immediately
      addMessage(currentTaskId, {
        id: `user-${Date.now()}`,
        task_id: currentTaskId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      })

      // Clear previous tool calls before new message
      clearToolCalls()

      // Send to backend (will process async and stream events)
      try {
        await apiClient.sendMessage(currentTaskId, content)
      } catch (err) {
        console.error('Failed to send message:', err)
      }
    },
    [currentTaskId, addMessage, clearToolCalls]
  )

  if (!currentTaskId) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
            <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/><path d="M9 20v2"/><path d="M15 20v2"/></svg>
          </div>
          <div>
            <p className="text-lg font-medium text-foreground">No task selected</p>
            <p className="text-sm mt-1">Create a new task to start chatting</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <MessageList messages={messages}>
        {/* Active tool calls */}
        {activeToolCalls.map((tc) => (
          <ToolCallDisplay
            key={tc.call_id}
            name={tc.name}
            status={tc.status}
            output={tc.output}
            is_error={tc.is_error}
          />
        ))}

        {/* Streaming response */}
        {streamingText && <StreamingMessage text={streamingText} />}
      </MessageList>

      {/* Token usage indicator */}
      {lastTokenUsage && (
        <div className="px-4 py-1 text-xs text-muted-foreground text-center">
          {lastTokenUsage.input_tokens.toLocaleString()} in / {lastTokenUsage.output_tokens.toLocaleString()} out
        </div>
      )}

      <MessageInput
        onSend={handleSend}
        disabled={isStreaming}
        placeholder={isStreaming ? 'Agent is thinking...' : undefined}
      />
    </div>
  )
}
