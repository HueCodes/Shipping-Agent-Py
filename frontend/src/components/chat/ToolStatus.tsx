import { Loader2, Check, Package, MapPin, Truck, Search } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { ToolStatus as ToolStatusType } from '../../stores/chatStore'

const toolConfig: Record<string, { label: string; icon: typeof Package }> = {
  get_shipping_rates: { label: 'Fetching shipping rates', icon: Search },
  get_rates: { label: 'Fetching shipping rates', icon: Search },
  create_shipment: { label: 'Creating shipping label', icon: Package },
  track_shipment: { label: 'Getting tracking info', icon: Truck },
  get_tracking_status: { label: 'Getting tracking info', icon: Truck },
  validate_address: { label: 'Validating address', icon: MapPin },
  get_orders: { label: 'Loading orders', icon: Package },
  get_unfulfilled_orders: { label: 'Loading orders', icon: Package },
}

interface ToolStatusProps {
  toolStatus: ToolStatusType
}

export function ToolStatus({ toolStatus }: ToolStatusProps) {
  const config = toolConfig[toolStatus.tool] || {
    label: `Running ${toolStatus.tool}`,
    icon: Package,
  }
  const Icon = config.icon
  const isComplete = toolStatus.status === 'complete'

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-lg text-sm animate-fade-in',
        'bg-bg-secondary border border-border text-text-muted'
      )}
    >
      {isComplete ? (
        <Check className="h-4 w-4 text-accent-green" />
      ) : (
        <Loader2 className="h-4 w-4 animate-spin text-accent-blue" />
      )}
      <Icon className="h-4 w-4" />
      <span>{config.label}{isComplete ? '' : '...'}</span>
    </div>
  )
}

interface StatusMessageProps {
  message: string
}

export function StatusMessage({ message }: StatusMessageProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm bg-bg-secondary border border-border text-text-muted animate-fade-in">
      <Loader2 className="h-4 w-4 animate-spin text-accent-blue" />
      <span>{message}</span>
    </div>
  )
}
