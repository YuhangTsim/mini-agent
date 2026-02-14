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
        <div className="text-center space-y-2">
          <p className="text-lg">No task selected</p>
          <p className="text-sm">Create a new task to start chatting</p>
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
