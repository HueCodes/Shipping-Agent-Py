import { Calendar, Package } from 'lucide-react'
import { Card, Badge } from '../ui'
import { TrackingEvent } from './TrackingEvent'
import { TrackingStatusBadge } from './TrackingStatusBadge'
import { CarrierBadge } from '../rates/CarrierLogo'
import { formatDate, cn } from '../../lib/utils'
import type { TrackingResponse } from '../../api/types'

interface TrackingTimelineProps {
  tracking: TrackingResponse
  className?: string
}

export function TrackingTimeline({ tracking, className }: TrackingTimelineProps) {
  // Reverse events so newest is first
  const events = [...tracking.events].reverse()

  return (
    <Card className={cn('overflow-hidden', className)}>
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-3">
          <CarrierBadge carrier={tracking.carrier} />
          <TrackingStatusBadge status={tracking.status} size="lg" />
        </div>

        {/* Tracking number */}
        <div className="flex items-center gap-2 mb-3">
          <Package className="h-4 w-4 text-text-dim" />
          <code className="text-sm text-text-primary font-mono">
            {tracking.tracking_number}
          </code>
        </div>

        {/* Estimated delivery */}
        {tracking.estimated_delivery && (
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4 text-text-dim" />
            <span className="text-text-muted">Estimated delivery:</span>
            <span className="text-text-primary font-medium">
              {formatDate(tracking.estimated_delivery)}
            </span>
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="p-4">
        {events.length > 0 ? (
          <div>
            {events.map((event, index) => (
              <TrackingEvent
                key={`${event.occurred_at}-${index}`}
                event={event}
                isLatest={index === 0}
                isLast={index === events.length - 1}
              />
            ))}
          </div>
        ) : (
          <div className="text-center text-text-dim py-4">
            No tracking events yet
          </div>
        )}
      </div>
    </Card>
  )
}

// Compact inline version
export function TrackingTimelineCompact({ tracking }: { tracking: TrackingResponse }) {
  const latestEvent = tracking.events[tracking.events.length - 1]

  return (
    <div className="flex items-center gap-3">
      <TrackingStatusBadge status={tracking.status} size="sm" />
      {latestEvent && (
        <span className="text-xs text-text-dim">
          {latestEvent.status.replace(/_/g, ' ')}
          {latestEvent.location &&
            ` - ${
              typeof latestEvent.location === 'string'
                ? latestEvent.location
                : latestEvent.location.city
            }`}
        </span>
      )}
    </div>
  )
}
