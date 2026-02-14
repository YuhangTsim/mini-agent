/**
 * Server-Sent Events (SSE) handler for real-time streaming
 */

import type { SSEEvent, SSEEventType } from './types';

export type SSEEventHandler = (event: SSEEvent) => void;

export class SSEConnection {
  private eventSource: EventSource | null = null;
  private handlers: Map<SSEEventType | '*', Set<SSEEventHandler>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // Start with 1 second
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect(): void {
    if (this.eventSource) {
      console.warn('SSE already connected');
      return;
    }

    console.log('Connecting to SSE:', this.url);
    this.eventSource = new EventSource(this.url);

    this.eventSource.onopen = () => {
      console.log('SSE connected');
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      this.handleReconnect();
    };

    // Listen for all event types
    const eventTypes: SSEEventType[] = [
      'connected',
      'token_stream',
      'tool_call_start',
      'tool_call_end',
      'tool_approval_required',
      'user_input_required',
      'message_end',
      'task_status_changed',
      'ping',
    ];

    eventTypes.forEach((type) => {
      this.eventSource!.addEventListener(type, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          this.emit({ type, data });
        } catch (err) {
          console.error(`Failed to parse SSE event (${type}):`, err);
        }
      });
    });
  }

  private handleReconnect(): void {
    this.disconnect();

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max SSE reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff

    console.log(`Reconnecting SSE in ${delay}ms (attempt ${this.reconnectAttempts})`);
    setTimeout(() => this.connect(), delay);
  }

  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  on(eventType: SSEEventType | '*', handler: SSEEventHandler): void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);
  }

  off(eventType: SSEEventType | '*', handler: SSEEventHandler): void {
    const handlers = this.handlers.get(eventType);
    if (handlers) {
      handlers.delete(handler);
    }
  }

  private emit(event: SSEEvent): void {
    // Call specific event type handlers
    const typeHandlers = this.handlers.get(event.type);
    if (typeHandlers) {
      typeHandlers.forEach((handler) => handler(event));
    }

    // Call wildcard handlers
    const wildcardHandlers = this.handlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => handler(event));
    }
  }
}
