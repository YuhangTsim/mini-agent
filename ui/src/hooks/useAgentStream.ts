/**
 * Hook to subscribe to SSE events for a task
 */

import { useEffect, useRef } from 'react'
import { SSEConnection } from '../lib/api/sse'
import { useAgentStore } from '../lib/store/agent'
import { useUIStore } from '../lib/store/ui'

export function useAgentStream(taskId: string | null) {
  const connectionRef = useRef<SSEConnection | null>(null)

  const appendStreamingText = useAgentStore((s) => s.appendStreamingText)
  const clearStreamingText = useAgentStore((s) => s.clearStreamingText)
  const setIsStreaming = useAgentStore((s) => s.setIsStreaming)
  const addToolCall = useAgentStore((s) => s.addToolCall)
  const updateToolCall = useAgentStore((s) => s.updateToolCall)
  const setTokenUsage = useAgentStore((s) => s.setTokenUsage)
  const addMessage = useAgentStore((s) => s.addMessage)
  const addApproval = useUIStore((s) => s.addApproval)
  const setInputRequest = useUIStore((s) => s.setInputRequest)

  useEffect(() => {
    if (!taskId) return

    // Clean up any existing connection
    if (connectionRef.current) {
      connectionRef.current.disconnect()
    }

    const conn = new SSEConnection(`/api/tasks/${taskId}/stream`)
    connectionRef.current = conn

    conn.on('connected', () => {
      console.log('SSE stream connected for task:', taskId)
    })

    conn.on('token_stream', (event) => {
      setIsStreaming(true)
      appendStreamingText(event.data.text)
    })

    conn.on('tool_call_start', (event) => {
      addToolCall({
        call_id: event.data.call_id,
        name: event.data.name,
        status: 'running',
      })
    })

    conn.on('tool_call_end', (event) => {
      updateToolCall(event.data.call_id, {
        status: event.data.is_error ? 'error' : 'completed',
        output: event.data.output,
        is_error: event.data.is_error,
      })
    })

    conn.on('tool_approval_required', (event) => {
      addApproval({
        approval_id: event.data.approval_id,
        tool_name: event.data.tool,
        params: event.data.params,
      })
    })

    conn.on('user_input_required', (event) => {
      setInputRequest({
        input_id: event.data.input_id,
        question: event.data.question,
        suggestions: event.data.suggestions || [],
      })
    })

    conn.on('message_end', (event) => {
      setIsStreaming(false)
      setTokenUsage({
        input_tokens: event.data.input_tokens,
        output_tokens: event.data.output_tokens,
      })

      // Handle error from backend
      if (event.data.error) {
        addMessage(taskId, {
          id: `err-${Date.now()}`,
          task_id: taskId,
          role: 'assistant',
          content: `**Error:** ${event.data.error}`,
          created_at: new Date().toISOString(),
        })
        clearStreamingText()
        return
      }

      // Flush streaming text into a message
      const streamingText = useAgentStore.getState().streamingText
      if (streamingText) {
        addMessage(taskId, {
          id: `msg-${Date.now()}`,
          task_id: taskId,
          role: 'assistant',
          content: streamingText,
          created_at: new Date().toISOString(),
        })
        clearStreamingText()
      }
    })

    conn.connect()

    return () => {
      conn.disconnect()
      connectionRef.current = null
    }
  }, [taskId])
}
