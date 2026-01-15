import { cn } from '../../lib/utils'
import type { Message } from '../../stores/chatStore'

interface ChatMessageProps {
  message: Message
}

export function ChatMessage({ message }: ChatMessageProps) {
  const { role, content, isStreaming } = message

  if (role === 'system') {
    return (
      <div className="text-center text-sm text-text-dim py-2 animate-fade-in">
        {content}
      </div>
    )
  }

  const isUser = role === 'user'

  return (
    <div
      className={cn(
        'max-w-[80%] px-4 py-3 rounded-xl animate-fade-in',
        isUser
          ? 'bg-accent-blue text-white self-end rounded-br-sm'
          : 'bg-bg-secondary border border-border self-start rounded-bl-sm'
      )}
    >
      <div
        className={cn('text-sm leading-relaxed', {
          'text-text-secondary': !isUser,
        })}
      >
        <MessageContent content={content} isUser={isUser} />
      </div>
      {isStreaming && (
        <span className="inline-block w-1.5 h-4 ml-0.5 bg-accent-blue animate-pulse" />
      )}
    </div>
  )
}

function MessageContent({ content, isUser }: { content: string; isUser: boolean }) {
  // Simple markdown-like parsing
  const parts = content.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`|\n)/g)

  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return (
            <strong key={i} className={cn(!isUser && 'text-text-primary')}>
              {part.slice(2, -2)}
            </strong>
          )
        }
        if (part.startsWith('*') && part.endsWith('*')) {
          return <em key={i}>{part.slice(1, -1)}</em>
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return (
            <code
              key={i}
              className={cn(
                'px-1 py-0.5 rounded text-xs font-mono',
                isUser ? 'bg-blue-600' : 'bg-bg-primary'
              )}
            >
              {part.slice(1, -1)}
            </code>
          )
        }
        if (part === '\n') {
          return <br key={i} />
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
