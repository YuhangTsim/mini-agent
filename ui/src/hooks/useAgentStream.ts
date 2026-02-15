import { useEffect, useRef } from 'react'
import { SSEConnection } from '../lib/api/sse'
import { useAgentStore } from '../lib/store/agent'
import { useUIStore } from '../lib/store/ui'

export function useAgentStream(taskId: string | null) {
  const connectionRef = useRef<SSEConnection | null>(null)

  useEffect(() => {
    if (!taskId) return

    const store = useAgentStore.getState()
    const uiStore = useUIStore.getState()

    if (connectionRef.current) {
      connectionRef.current.disconnect()
    }

    const conn = new SSEConnection(`/api/tasks/${taskId}/stream`)
    connectionRef.current = conn

    conn.on('connected', () => {
      console.log('SSE stream connected for task:', taskId)
    })

    conn.on('token_stream', (event) => {
      store.setIsStreaming(true)
      store.appendStreamingText(event.data.text)
    })

    conn.on('tool_call_start', (event) => {
      store.addToolCall({
        call_id: event.data.call_id,
        name: event.data.name,
        status: 'running',
      })
    })

    conn.on('tool_call_end', (event) => {
      store.updateToolCall(event.data.call_id, {
        status: event.data.is_error ? 'error' : 'completed',
        output: event.data.output,
        is_error: event.data.is_error,
      })
    })

    conn.on('tool_approval_required', (event) => {
      uiStore.addApproval({
        approval_id: event.data.approval_id,
        tool_name: event.data.tool,
        params: event.data.params,
      })
    })

    conn.on('user_input_required', (event) => {
      uiStore.setInputRequest({
        input_id: event.data.input_id,
        question: event.data.question,
        suggestions: event.data.suggestions || [],
      })
    })

    conn.on('message_end', (event) => {
      store.setIsStreaming(false)
      store.setTokenUsage({
        input_tokens: event.data.input_tokens,
        output_tokens: event.data.output_tokens,
      })

      if (event.data.error) {
        store.addMessage(taskId, {
          id: `err-${Date.now()}`,
          task_id: taskId,
          role: 'assistant',
          content: `**Error:** ${event.data.error}`,
          created_at: new Date().toISOString(),
        })
        store.clearStreamingText()
        return
      }

      const streamingText = useAgentStore.getState().streamingText
      if (streamingText) {
        store.addMessage(taskId, {
          id: `msg-${Date.now()}`,
          task_id: taskId,
          role: 'assistant',
          content: streamingText,
          created_at: new Date().toISOString(),
        })
        store.clearStreamingText()
      }
    })

    conn.connect()

    return () => {
      conn.disconnect()
      connectionRef.current = null
    }
  }, [taskId])
}
