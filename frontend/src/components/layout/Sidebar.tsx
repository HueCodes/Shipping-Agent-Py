import { X } from 'lucide-react'
import { cn } from '../../lib/utils'
import { useUIStore } from '../../stores/uiStore'
import { SearchInput, ScrollArea } from '../ui'
import { OrderList } from '../orders/OrderList'

export function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen)
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen)

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed md:static inset-y-0 left-0 z-50 w-80 bg-bg-secondary border-r border-border',
          'flex flex-col transition-transform duration-300',
          'md:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-base font-semibold text-text-primary">Orders</h2>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1.5 text-text-muted hover:text-text-secondary hover:bg-bg-tertiary rounded-md transition-colors md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-3 border-b border-border">
          <SearchInput placeholder="Search orders..." />
        </div>

        <ScrollArea className="flex-1 p-2">
          <OrderList />
        </ScrollArea>
      </aside>
    </>
  )
}
