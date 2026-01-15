import { cn } from '../../lib/utils'
import { getCarrierInfo } from '../../lib/carriers'

interface CarrierLogoProps {
  carrier: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function CarrierLogo({ carrier, size = 'md', className }: CarrierLogoProps) {
  const info = getCarrierInfo(carrier)

  const sizeClasses = {
    sm: 'h-6 w-6 text-xs',
    md: 'h-8 w-8 text-sm',
    lg: 'h-10 w-10 text-base',
  }

  // For now, use text abbreviations with carrier colors
  // Can be replaced with actual SVG logos later
  const abbreviation = carrier.substring(0, 2).toUpperCase()

  return (
    <div
      className={cn(
        'flex items-center justify-center rounded font-bold',
        info.bgColor,
        info.textColor,
        sizeClasses[size],
        className
      )}
      title={info.name}
    >
      {abbreviation}
    </div>
  )
}

// Full carrier badge with name
export function CarrierBadge({ carrier, className }: { carrier: string; className?: string }) {
  const info = getCarrierInfo(carrier)

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-2 py-1 rounded',
        info.bgColor,
        className
      )}
    >
      <CarrierLogo carrier={carrier} size="sm" />
      <span className={cn('text-xs font-medium', info.textColor)}>
        {info.name}
      </span>
    </div>
  )
}
