import { cn } from '../../lib/utils'

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3 bg-bg-secondary border border-border rounded-xl rounded-bl-sm w-fit animate-fade-in">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cn(
            'h-2 w-2 rounded-full bg-text-dim animate-bounce-dots',
          )}
          style={{ animationDelay: `${-0.32 + i * 0.16}s` }}
        />
      ))}
    </div>
  )
}
