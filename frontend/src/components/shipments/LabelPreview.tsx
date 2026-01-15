import { X, ExternalLink } from 'lucide-react'
import { Card, Badge, Button } from '../ui'
import { LabelActions } from './LabelActions'
import { CarrierBadge } from '../rates/CarrierLogo'
import { cn, formatCurrency } from '../../lib/utils'
import type { Shipment } from '../../api/types'

interface LabelPreviewProps {
  shipment: Shipment
  onClose?: () => void
  className?: string
}

export function LabelPreview({ shipment, onClose, className }: LabelPreviewProps) {
  if (!shipment.label_url) {
    return (
      <Card className={cn('p-6', className)}>
        <p className="text-text-muted text-center">No label available</p>
      </Card>
    )
  }

  return (
    <Card className={cn('overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <CarrierBadge carrier={shipment.carrier} />
          <div>
            <div className="text-sm font-medium text-text-primary">
              {shipment.service}
            </div>
            {shipment.rate_amount && (
              <div className="text-xs text-accent-green">
                {formatCurrency(shipment.rate_amount)}
              </div>
            )}
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-text-muted hover:text-text-secondary hover:bg-bg-tertiary rounded-md transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Label Preview */}
      <div className="p-4 bg-bg-primary">
        <div className="aspect-[8.5/11] bg-white rounded-lg overflow-hidden shadow-lg">
          <iframe
            src={shipment.label_url}
            className="w-full h-full"
            title="Shipping Label"
          />
        </div>
      </div>

      {/* Footer with actions */}
      <div className="p-4 border-t border-border space-y-3">
        {/* Tracking number */}
        {shipment.tracking_number && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-muted">Tracking Number</span>
            <div className="flex items-center gap-2">
              <code className="px-2 py-1 bg-bg-primary rounded text-sm text-text-primary font-mono">
                {shipment.tracking_number}
              </code>
            </div>
          </div>
        )}

        {/* Status */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-muted">Status</span>
          <Badge variant="success">{shipment.status}</Badge>
        </div>

        {/* Actions */}
        {shipment.tracking_number && (
          <LabelActions
            labelUrl={shipment.label_url}
            trackingNumber={shipment.tracking_number}
            className="pt-2"
          />
        )}

        {/* Open in new tab */}
        <a
          href={shipment.label_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 text-sm text-accent-blue hover:underline"
        >
          <ExternalLink className="h-4 w-4" />
          Open label in new tab
        </a>
      </div>
    </Card>
  )
}

// Compact version for inline display
export function LabelPreviewCompact({ shipment }: { shipment: Shipment }) {
  if (!shipment.label_url || !shipment.tracking_number) {
    return null
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <CarrierBadge carrier={shipment.carrier} />
        <Badge variant="success">{shipment.status}</Badge>
      </div>

      <div className="mb-3">
        <div className="text-xs text-text-dim mb-1">Tracking Number</div>
        <code className="text-sm text-text-primary font-mono">
          {shipment.tracking_number}
        </code>
      </div>

      <LabelActions
        labelUrl={shipment.label_url}
        trackingNumber={shipment.tracking_number}
      />
    </Card>
  )
}
