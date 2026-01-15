import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'outline'
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium',
        {
          'bg-bg-tertiary text-text-muted': variant === 'default',
          'bg-green-900/50 text-green-300': variant === 'success',
          'bg-amber-900/50 text-amber-300': variant === 'warning',
          'bg-red-900/50 text-red-300': variant === 'error',
          'bg-blue-900/50 text-blue-300': variant === 'info',
          'border border-border bg-transparent text-text-muted': variant === 'outline',
        },
        className
      )}
      {...props}
    />
  )
}

// Specialized status badges
export function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, BadgeProps['variant']> = {
    unfulfilled: 'warning',
    fulfilled: 'success',
    shipped: 'success',
    partial: 'info',
    processing: 'info',
    delivered: 'success',
    in_transit: 'info',
    out_for_delivery: 'info',
    exception: 'error',
    cancelled: 'error',
  }

  const labels: Record<string, string> = {
    unfulfilled: 'Unfulfilled',
    fulfilled: 'Fulfilled',
    shipped: 'Shipped',
    partial: 'Partial',
    processing: 'Processing',
    delivered: 'Delivered',
    in_transit: 'In Transit',
    out_for_delivery: 'Out for Delivery',
    exception: 'Exception',
    cancelled: 'Cancelled',
  }

  return (
    <Badge variant={variants[status] || 'default'}>
      {labels[status] || status}
    </Badge>
  )
}

// Connection status badge
export function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium',
        'bg-bg-tertiary text-text-muted'
      )}
    >
      <span
        className={cn('h-1.5 w-1.5 rounded-full', {
          'bg-accent-green': connected,
          'bg-accent-red': !connected,
        })}
      />
      {connected ? 'Live' : 'Offline'}
    </span>
  )
}

// Mode badge (MOCK/LIVE)
export function ModeBadge({ mockMode }: { mockMode: boolean }) {
  return (
    <span
      className={cn('rounded-md px-2 py-0.5 text-xs font-medium', {
        'bg-amber-900/50 text-amber-200': mockMode,
        'bg-green-900/50 text-green-200': !mockMode,
      })}
    >
      {mockMode ? 'MOCK' : 'LIVE'}
    </span>
  )
}
