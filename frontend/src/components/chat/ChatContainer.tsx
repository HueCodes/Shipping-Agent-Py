import { useEffect, useRef } from 'react'
import { useChat } from '../../hooks/useChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { ToolStatus, StatusMessage } from './ToolStatus'
import { ScrollArea } from '../ui'

export function ChatContainer() {
  const {
    messages,
    isStreaming,
    currentToolStatus,
    statusMessage,
    sendMessage,
  } = useChat()

  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming, currentToolStatus, statusMessage])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <ScrollArea ref={scrollRef} className="flex-1 p-4">
        <div className="max-w-3xl mx-auto flex flex-col gap-3">
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {/* Status indicators */}
          {statusMessage && !currentToolStatus && (
            <StatusMessage message={statusMessage} />
          )}

          {currentToolStatus && (
            <ToolStatus toolStatus={currentToolStatus} />
          )}

          {isStreaming && !messages.some((m) => m.isStreaming) && (
            <TypingIndicator />
          )}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
