import {
  Package,
  Truck,
  CheckCircle,
  AlertTriangle,
  MapPin,
  Clock,
} from 'lucide-react'
import { Badge } from '../ui'
import { cn } from '../../lib/utils'
import { getStatusCategory } from '../../hooks/useTracking'

interface TrackingStatusBadgeProps {
  status: string
  size?: 'sm' | 'md' | 'lg'
}

export function TrackingStatusBadge({ status, size = 'md' }: TrackingStatusBadgeProps) {
  const category = getStatusCategory(status)

  const variants = {
    pending: 'default',
    transit: 'info',
    delivered: 'success',
    exception: 'error',
  } as const

  const icons = {
    pending: Package,
    transit: Truck,
    delivered: CheckCircle,
    exception: AlertTriangle,
  }

  const Icon = icons[category]
  const sizeClasses = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-xs px-2 py-0.5',
    lg: 'text-sm px-2.5 py-1',
  }

  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-3.5 w-3.5',
    lg: 'h-4 w-4',
  }

  // Format status for display
  const displayStatus = status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <Badge variant={variants[category]} className={cn(sizeClasses[size])}>
      <Icon className={cn(iconSizes[size], 'mr-1')} />
      {displayStatus}
    </Badge>
  )
}

// Status icon only (for timeline dots)
export function TrackingStatusIcon({
  status,
  isLatest,
}: {
  status: string
  isLatest?: boolean
}) {
  const category = getStatusCategory(status)

  const bgColors = {
    pending: 'bg-slate-600',
    transit: 'bg-blue-500',
    delivered: 'bg-green-500',
    exception: 'bg-red-500',
  }

  return (
    <div
      className={cn(
        'h-3 w-3 rounded-full border-2',
        isLatest ? bgColors[category] : 'bg-bg-tertiary',
        isLatest ? 'border-bg-secondary' : 'border-border'
      )}
    />
  )
}
