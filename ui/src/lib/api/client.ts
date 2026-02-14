/**
 * HTTP client for Mini-Agent API
 */

import type { Task, Message, Mode, HealthResponse } from './types';

const API_BASE_URL = '/api';

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        error: 'Unknown error',
        detail: response.statusText,
      }));
      throw new Error(error.detail || error.error);
    }

    return response.json();
  }

  // Health
  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // Tasks
  async createTask(data: {
    description: string;
    mode?: string;
    title?: string;
    parent_id?: string;
  }): Promise<Task> {
    return this.request<Task>('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getTask(taskId: string): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}`);
  }

  async listTasks(params?: {
    parent_id?: string;
    status_filter?: string;
    limit?: number;
  }): Promise<{ tasks: Task[] }> {
    const query = new URLSearchParams();
    if (params?.parent_id) query.append('parent_id', params.parent_id);
    if (params?.status_filter) query.append('status_filter', params.status_filter);
    if (params?.limit) query.append('limit', params.limit.toString());

    const endpoint = `/tasks${query.toString() ? `?${query}` : ''}`;
    return this.request<{ tasks: Task[] }>(endpoint);
  }

  async cancelTask(taskId: string): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}`, {
      method: 'DELETE',
    });
  }

  async switchMode(taskId: string, mode: string): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}/mode`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  }

  // Messages
  async sendMessage(
    taskId: string,
    content: string
  ): Promise<{ status: string; message: string; task_id: string }> {
    return this.request(`/tasks/${taskId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async getMessages(taskId: string): Promise<{ messages: Message[] }> {
    return this.request<{ messages: Message[] }>(`/tasks/${taskId}/messages`);
  }

  // Modes
  async listModes(): Promise<{ modes: Mode[] }> {
    return this.request<{ modes: Mode[] }>('/modes');
  }

  // Approvals
  async respondToApproval(
    approvalId: string,
    decision: 'y' | 'n' | 'always'
  ): Promise<{ status: string }> {
    return this.request(`/approvals/${approvalId}`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    });
  }

  // User Input
  async respondToInput(inputId: string, answer: string): Promise<{ status: string }> {
    return this.request(`/inputs/${inputId}`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    });
  }

  // SSE Stream URL
  getStreamUrl(taskId: string): string {
    return `${this.baseUrl}/tasks/${taskId}/stream`;
  }
}

export const apiClient = new APIClient();
export default apiClient;
