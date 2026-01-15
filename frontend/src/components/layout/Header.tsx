import { Menu } from 'lucide-react'
import { Button, ConnectionBadge, ModeBadge } from '../ui'
import { useUIStore } from '../../stores/uiStore'
import { useChatStore } from '../../stores/chatStore'
import { useChat } from '../../hooks/useChat'

export function Header() {
  const toggleSidebar = useUIStore((s) => s.toggleSidebar)
  const mockMode = useUIStore((s) => s.mockMode)
  const isConnected = useChatStore((s) => s.isConnected)
  const { resetChat } = useChat()

  return (
    <header className="flex items-center justify-between px-4 py-3 bg-bg-secondary border-b border-border">
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="p-2 text-text-muted hover:text-text-secondary hover:bg-bg-tertiary rounded-md transition-colors md:hidden"
          aria-label="Toggle orders sidebar"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold text-text-primary">
          Shipping Agent
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <ConnectionBadge connected={isConnected} />
        <ModeBadge mockMode={mockMode} />
        <Button variant="default" size="sm" onClick={resetChat}>
          Reset
        </Button>
      </div>
    </header>
  )
}
