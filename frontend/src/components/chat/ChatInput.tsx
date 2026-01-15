import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'
import { Button, Input } from '../ui'
import { cn } from '../../lib/utils'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

const suggestions = [
  { label: 'Rates to LA', text: 'Get rates for a 2lb package to Los Angeles, CA' },
  { label: 'Rates to Chicago', text: 'How much to ship 32oz to Chicago?' },
  { label: 'Validate address', text: 'Validate address: 123 Main St, Miami, FL 33101' },
  { label: 'Overnight to NYC', text: "What's the cheapest overnight option to NYC?" },
]

export function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [message, setMessage] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (message.trim() && !disabled) {
      onSend(message.trim())
      setMessage('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
  }

  const handleSuggestionClick = (text: string) => {
    setMessage(text)
  }

  return (
    <div className="p-4 bg-bg-secondary border-t border-border">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        <div className="flex gap-3">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || 'Get rates for a 2lb package to Chicago...'}
            disabled={disabled}
            className="flex-1"
            autoComplete="off"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={disabled || !message.trim()}
            className="px-4"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion.label}
              type="button"
              onClick={() => handleSuggestionClick(suggestion.text)}
              className={cn(
                'px-3 py-1.5 rounded-md text-sm transition-colors',
                'bg-bg-tertiary text-slate-300 hover:bg-slate-600'
              )}
            >
              {suggestion.label}
            </button>
          ))}
        </div>
      </form>
    </div>
  )
}
