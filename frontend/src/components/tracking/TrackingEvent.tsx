import { MapPin } from 'lucide-react'
import { cn, formatRelativeTime } from '../../lib/utils'
import { TrackingStatusIcon } from './TrackingStatusBadge'
import type { TrackingEvent as TrackingEventType } from '../../api/types'

interface TrackingEventProps {
  event: TrackingEventType
  isLatest?: boolean
  isLast?: boolean
}

export function TrackingEvent({ event, isLatest, isLast }: TrackingEventProps) {
  // Format location
  const location = event.location
    ? typeof event.location === 'string'
      ? event.location
      : event.location.description ||
        [event.location.city, event.location.state].filter(Boolean).join(', ')
    : null

  // Format status for display
  const displayStatus = event.status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div className="relative flex gap-3 pb-4">
      {/* Timeline line */}
      {!isLast && (
        <div className="absolute left-[5px] top-4 bottom-0 w-0.5 bg-border" />
      )}

      {/* Status dot */}
      <div className="relative z-10 mt-1">
        <TrackingStatusIcon status={event.status} isLatest={isLatest} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div
          className={cn(
            'font-medium text-sm',
            isLatest ? 'text-text-primary' : 'text-text-secondary'
          )}
        >
          {displayStatus}
        </div>

        {event.description && (
          <div className="text-xs text-text-muted mt-0.5">
            {event.description}
          </div>
        )}

        <div className="flex items-center gap-3 mt-1 text-xs text-text-dim">
          {location && (
            <span className="flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {location}
            </span>
          )}
          <span>{formatRelativeTime(event.occurred_at)}</span>
        </div>
      </div>
    </div>
  )
}
