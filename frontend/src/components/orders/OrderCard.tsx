import { Package } from 'lucide-react'
import { cn } from '../../lib/utils'
import { Card, StatusBadge } from '../ui'
import type { Order } from '../../api/types'

interface OrderCardProps {
  order: Order
  isSelected?: boolean
  onClick?: () => void
}

export function OrderCard({ order, isSelected, onClick }: OrderCardProps) {
  const itemCount = order.line_items?.reduce(
    (sum, item) => sum + (item.quantity || 1),
    0
  ) ?? 0

  return (
    <Card
      variant={isSelected ? 'selected' : 'interactive'}
      className="p-3 mb-2"
      onClick={onClick}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-text-primary">
          {order.order_number || `#${order.shopify_order_id}`}
        </span>
        <StatusBadge status={order.status} />
      </div>

      <div className="text-sm text-text-secondary mb-1 truncate">
        {order.recipient_name || 'No recipient'}
      </div>

      <div className="flex items-center gap-2 text-xs text-text-dim">
        <Package className="h-3 w-3" />
        <span>
          {itemCount} item{itemCount !== 1 ? 's' : ''}
        </span>
        {order.weight_oz && (
          <>
            <span className="text-border">|</span>
            <span>{order.weight_oz.toFixed(1)} oz</span>
          </>
        )}
      </div>

      {order.shipping_address && (
        <div className="text-xs text-text-dim mt-1 truncate">
          {order.shipping_address.city}, {order.shipping_address.state}
        </div>
      )}
    </Card>
  )
}
