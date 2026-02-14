/**
 * Zustand store for agent state (tasks, messages, streaming)
 */

import { create } from 'zustand'
import type { Task, Message, TokenUsage } from '../api/types'

interface ToolCallState {
  call_id: string;
  name: string;
  status: 'running' | 'completed' | 'error';
  output?: string;
  is_error?: boolean;
}

interface AgentState {
  // Current task
  currentTaskId: string | null;
  tasks: Map<string, Task>;

  // Messages per task
  messages: Map<string, Message[]>;

  // Streaming state
  streamingText: string;
  isStreaming: boolean;

  // Active tool calls
  activeToolCalls: ToolCallState[];

  // Token usage for current response
  lastTokenUsage: TokenUsage | null;

  // Actions
  setCurrentTask: (taskId: string) => void;
  addTask: (task: Task) => void;
  updateTask: (task: Task) => void;

  addMessage: (taskId: string, message: Message) => void;
  setMessages: (taskId: string, messages: Message[]) => void;

  appendStreamingText: (text: string) => void;
  clearStreamingText: () => void;
  setIsStreaming: (streaming: boolean) => void;

  addToolCall: (toolCall: ToolCallState) => void;
  updateToolCall: (callId: string, update: Partial<ToolCallState>) => void;
  clearToolCalls: () => void;

  setTokenUsage: (usage: TokenUsage) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  currentTaskId: null,
  tasks: new Map(),
  messages: new Map(),
  streamingText: '',
  isStreaming: false,
  activeToolCalls: [],
  lastTokenUsage: null,

  setCurrentTask: (taskId) => set({ currentTaskId: taskId }),

  addTask: (task) =>
    set((state) => {
      const tasks = new Map(state.tasks);
      tasks.set(task.id, task);
      return { tasks };
    }),

  updateTask: (task) =>
    set((state) => {
      const tasks = new Map(state.tasks);
      tasks.set(task.id, task);
      return { tasks };
    }),

  addMessage: (taskId, message) =>
    set((state) => {
      const messages = new Map(state.messages);
      const taskMessages = [...(messages.get(taskId) || []), message];
      messages.set(taskId, taskMessages);
      return { messages };
    }),

  setMessages: (taskId, msgs) =>
    set((state) => {
      const messages = new Map(state.messages);
      messages.set(taskId, msgs);
      return { messages };
    }),

  appendStreamingText: (text) =>
    set((state) => ({ streamingText: state.streamingText + text })),

  clearStreamingText: () => set({ streamingText: '' }),

  setIsStreaming: (streaming) => set({ isStreaming: streaming }),

  addToolCall: (toolCall) =>
    set((state) => ({
      activeToolCalls: [...state.activeToolCalls, toolCall],
    })),

  updateToolCall: (callId, update) =>
    set((state) => ({
      activeToolCalls: state.activeToolCalls.map((tc) =>
        tc.call_id === callId ? { ...tc, ...update } : tc
      ),
    })),

  clearToolCalls: () => set({ activeToolCalls: [] }),

  setTokenUsage: (usage) => set({ lastTokenUsage: usage }),
}))
