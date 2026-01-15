import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

export interface ToolStatus {
  tool: string
  status: 'start' | 'complete'
  success?: boolean
}

interface ChatState {
  messages: Message[]
  isStreaming: boolean
  isConnected: boolean
  currentToolStatus: ToolStatus | null
  statusMessage: string | null

  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => string
  updateMessage: (id: string, content: string) => void
  appendToMessage: (id: string, chunk: string) => void
  finalizeMessage: (id: string, content: string) => void
  setStreaming: (streaming: boolean) => void
  setConnected: (connected: boolean) => void
  setToolStatus: (status: ToolStatus | null) => void
  setStatusMessage: (message: string | null) => void
  clearMessages: () => void
  loadMessages: (messages: Message[]) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  isConnected: false,
  currentToolStatus: null,
  statusMessage: null,

  addMessage: (message) => {
    const id = `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
    const newMessage: Message = {
      ...message,
      id,
      timestamp: new Date(),
    }
    set((state) => ({
      messages: [...state.messages, newMessage],
    }))
    return id
  },

  updateMessage: (id, content) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content } : msg
      ),
    }))
  },

  appendToMessage: (id, chunk) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content: msg.content + chunk } : msg
      ),
    }))
  },

  finalizeMessage: (id, content) => {
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, content, isStreaming: false } : msg
      ),
      isStreaming: false,
    }))
  },

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  setConnected: (connected) => set({ isConnected: connected }),

  setToolStatus: (status) => set({ currentToolStatus: status }),

  setStatusMessage: (message) => set({ statusMessage: message }),

  clearMessages: () =>
    set({
      messages: [
        {
          id: 'welcome',
          role: 'system',
          content: 'Ask me about shipping rates, address validation, or creating labels.',
          timestamp: new Date(),
        },
      ],
    }),

  loadMessages: (messages) => set({ messages }),
}))
