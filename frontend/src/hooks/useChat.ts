import { useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChatWebSocket } from '../api/websocket'
import { api } from '../api/client'
import { useChatStore } from '../stores/chatStore'
import { useSessionStore } from '../stores/sessionStore'
import type { WSMessage } from '../api/types'

export function useChat() {
  const wsRef = useRef<ChatWebSocket | null>(null)
  const streamingMessageId = useRef<string | null>(null)

  const sessionId = useSessionStore((s) => s.sessionId)
  const {
    messages,
    isStreaming,
    isConnected,
    currentToolStatus,
    statusMessage,
    addMessage,
    appendToMessage,
    finalizeMessage,
    setStreaming,
    setConnected,
    setToolStatus,
    setStatusMessage,
    clearMessages,
    loadMessages,
  } = useChatStore()

  // Load chat history on mount
  const { data: historyData } = useQuery({
    queryKey: ['chatHistory', sessionId],
    queryFn: () => api.getChatHistory(sessionId),
    staleTime: Infinity, // Only fetch once
  })

  useEffect(() => {
    if (historyData?.messages && historyData.messages.length > 0) {
      const loaded = historyData.messages.map((msg, idx) => ({
        id: `history_${idx}`,
        role: msg.role as 'user' | 'assistant' | 'system',
        content: msg.content,
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      }))
      loadMessages(loaded)
    } else {
      clearMessages()
    }
  }, [historyData])

  // Handle WebSocket messages
  const handleMessage = useCallback(
    (data: WSMessage) => {
      switch (data.type) {
        case 'status':
          setStatusMessage(data.message)
          break

        case 'tool_start':
          setToolStatus({ tool: data.tool, status: 'start' })
          break

        case 'tool_complete':
          setToolStatus({ tool: data.tool, status: 'complete', success: data.success })
          // Clear after a short delay
          setTimeout(() => setToolStatus(null), 500)
          break

        case 'chunk':
          setStatusMessage(null)
          if (!streamingMessageId.current) {
            streamingMessageId.current = addMessage({
              role: 'assistant',
              content: '',
              isStreaming: true,
            })
          }
          appendToMessage(streamingMessageId.current, data.content)
          break

        case 'complete':
          setStatusMessage(null)
          setToolStatus(null)
          if (streamingMessageId.current) {
            finalizeMessage(
              streamingMessageId.current,
              data.content ||
                useChatStore.getState().messages.find(
                  (m) => m.id === streamingMessageId.current
                )?.content ||
                ''
            )
          }
          streamingMessageId.current = null
          break

        case 'error':
          setStatusMessage(null)
          setToolStatus(null)
          addMessage({
            role: 'system',
            content: data.message || 'An error occurred',
          })
          setStreaming(false)
          streamingMessageId.current = null
          break
      }
    },
    [addMessage, appendToMessage, finalizeMessage, setStatusMessage, setToolStatus, setStreaming]
  )

  // Initialize WebSocket
  useEffect(() => {
    wsRef.current = new ChatWebSocket(handleMessage, setConnected)
    wsRef.current.connect()

    return () => {
      wsRef.current?.disconnect()
    }
  }, [handleMessage, setConnected])

  // Send message
  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isStreaming) return

      // Add user message immediately
      addMessage({ role: 'user', content: text })
      setStreaming(true)
      setStatusMessage('Processing your request...')

      // Try WebSocket first
      if (wsRef.current?.isConnected) {
        wsRef.current.send(text, sessionId)
      } else {
        // Fallback to REST API
        try {
          const response = await api.sendMessage({
            message: text,
            session_id: sessionId,
          })
          addMessage({ role: 'assistant', content: response.response })
        } catch (err) {
          addMessage({
            role: 'system',
            content: `Error: ${err instanceof Error ? err.message : 'Something went wrong'}`,
          })
        } finally {
          setStreaming(false)
          setStatusMessage(null)
        }
      }
    },
    [sessionId, isStreaming, addMessage, setStreaming, setStatusMessage]
  )

  // Reset chat
  const resetChat = useCallback(async () => {
    try {
      await api.resetChat(sessionId)
      clearMessages()
    } catch (err) {
      console.error('Failed to reset chat:', err)
    }
  }, [sessionId, clearMessages])

  return {
    messages,
    isStreaming,
    isConnected,
    currentToolStatus,
    statusMessage,
    sendMessage,
    resetChat,
  }
}
