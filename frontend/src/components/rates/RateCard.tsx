import { Clock, Zap, DollarSign } from 'lucide-react'
import { cn, formatCurrency, getDeliveryDate } from '../../lib/utils'
import { Card, Badge } from '../ui'
import { CarrierLogo } from './CarrierLogo'
import type { Rate } from '../../api/types'

interface RateCardProps {
  rate: Rate
  isSelected?: boolean
  isBestValue?: boolean
  isFastest?: boolean
  onSelect?: (rateId: string) => void
}

export function RateCard({
  rate,
  isSelected,
  isBestValue,
  isFastest,
  onSelect,
}: RateCardProps) {
  const deliveryDate = getDeliveryDate(rate.delivery_days)

  return (
    <Card
      variant={isSelected ? 'selected' : 'interactive'}
      className={cn('p-4 relative', onSelect && 'cursor-pointer')}
      onClick={() => onSelect?.(rate.rate_id)}
    >
      {/* Badges */}
      <div className="absolute top-2 right-2 flex gap-1">
        {isBestValue && (
          <Badge variant="success" className="text-[10px] px-1.5">
            <DollarSign className="h-3 w-3 mr-0.5" />
            Best Value
          </Badge>
        )}
        {isFastest && !isBestValue && (
          <Badge variant="info" className="text-[10px] px-1.5">
            <Zap className="h-3 w-3 mr-0.5" />
            Fastest
          </Badge>
        )}
      </div>

      {/* Carrier and Service */}
      <div className="flex items-start gap-3 mb-3">
        <CarrierLogo carrier={rate.carrier} size="lg" />
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-text-primary text-sm">
            {rate.carrier}
          </div>
          <div className="text-xs text-text-muted truncate">{rate.service}</div>
        </div>
      </div>

      {/* Price */}
      <div className="text-xl font-bold text-accent-green mb-2">
        {formatCurrency(rate.price)}
      </div>

      {/* Delivery estimate */}
      {rate.delivery_days !== null && (
        <div className="flex items-center gap-1.5 text-xs text-text-dim">
          <Clock className="h-3 w-3" />
          <span>
            {rate.delivery_days} day{rate.delivery_days !== 1 ? 's' : ''}
            {deliveryDate && ` (by ${deliveryDate})`}
          </span>
        </div>
      )}

      {/* Selection indicator */}
      {isSelected && (
        <div className="absolute inset-0 rounded-lg ring-2 ring-accent-blue pointer-events-none" />
      )}
    </Card>
  )
}
