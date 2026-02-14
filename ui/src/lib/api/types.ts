/**
 * TypeScript types for Mini-Agent API
 * These correspond to the Pydantic schemas in the backend
 */

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface TodoItem {
  text: string;
  done: boolean;
}

export interface Task {
  id: string;
  parent_id: string | null;
  root_id: string | null;
  mode: string;
  status: string;
  title: string;
  description: string;
  working_directory: string;
  created_at: string;
  updated_at: string;
  token_usage: TokenUsage;
  todo_list: TodoItem[];
}

export interface Message {
  id: string;
  task_id: string;
  role: string;
  content: string;
  created_at: string;
  tool_calls?: any[];
}

export interface Mode {
  slug: string;
  name: string;
  when_to_use: string;
  tool_groups: string[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
}

// Event types for SSE streaming
export type SSEEventType =
  | 'connected'
  | 'token_stream'
  | 'tool_call_start'
  | 'tool_call_end'
  | 'tool_approval_required'
  | 'user_input_required'
  | 'message_end'
  | 'task_status_changed'
  | 'ping';

export interface SSEEvent {
  type: SSEEventType;
  data: any;
}
