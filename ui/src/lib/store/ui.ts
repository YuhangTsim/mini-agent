/**
 * Zustand store for UI state (modals, sidebar, etc.)
 */

import { create } from 'zustand'

interface ToolApproval {
  approval_id: string;
  tool_name: string;
  params: Record<string, unknown>;
}

interface UserInputRequest {
  input_id: string;
  question: string;
  suggestions: string[];
}

interface UIState {
  // Sidebar
  sidebarOpen: boolean;
  toggleSidebar: () => void;

  // Modals
  currentModal: 'approval' | 'input' | 'mode' | null;
  setModal: (modal: 'approval' | 'input' | 'mode' | null) => void;

  // Tool approval queue
  approvalQueue: ToolApproval[];
  addApproval: (approval: ToolApproval) => void;
  removeApproval: (approvalId: string) => void;
  currentApproval: () => ToolApproval | null;

  // User input request
  inputRequest: UserInputRequest | null;
  setInputRequest: (request: UserInputRequest | null) => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  currentModal: null,
  setModal: (modal) => set({ currentModal: modal }),

  approvalQueue: [],
  addApproval: (approval) =>
    set((state) => ({
      approvalQueue: [...state.approvalQueue, approval],
      currentModal: 'approval',
    })),
  removeApproval: (approvalId) =>
    set((state) => {
      const queue = state.approvalQueue.filter((a) => a.approval_id !== approvalId);
      return {
        approvalQueue: queue,
        currentModal: queue.length > 0 ? 'approval' : null,
      };
    }),
  currentApproval: () => {
    const state = get();
    return state.approvalQueue[0] || null;
  },

  inputRequest: null,
  setInputRequest: (request) =>
    set({
      inputRequest: request,
      currentModal: request ? 'input' : null,
    }),
}))
