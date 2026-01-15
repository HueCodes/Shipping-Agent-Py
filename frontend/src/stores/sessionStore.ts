import { create } from 'zustand'
import { getSessionId } from '../lib/utils'

interface SessionState {
  sessionId: string
  customerId: string | null
  setCustomerId: (id: string | null) => void
  resetSession: () => void
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: getSessionId(),
  customerId: null,

  setCustomerId: (id) => set({ customerId: id }),

  resetSession: () => {
    const key = 'shippingAgentSessionId'
    const newId = `session_${Math.random().toString(36).substring(2, 11)}_${Date.now()}`
    localStorage.setItem(key, newId)
    set({ sessionId: newId })
  },
}))
