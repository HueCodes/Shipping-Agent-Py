import { cn } from '../../lib/utils'

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-bg-tertiary',
        className
      )}
    />
  )
}

// Pre-built skeleton patterns
export function OrderCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-bg-primary p-4">
      <div className="flex justify-between items-center mb-3">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="h-4 w-32 mb-2" />
      <Skeleton className="h-3 w-24" />
    </div>
  )
}

export function RateCardSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-bg-primary p-4">
      <div className="flex items-center gap-3 mb-3">
        <Skeleton className="h-8 w-8 rounded" />
        <div className="flex-1">
          <Skeleton className="h-4 w-16 mb-1" />
          <Skeleton className="h-3 w-24" />
        </div>
      </div>
      <Skeleton className="h-6 w-16 mb-2" />
      <Skeleton className="h-3 w-28" />
    </div>
  )
}

export function ChatMessageSkeleton() {
  return (
    <div className="flex gap-3">
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  )
}

export function TrackingEventSkeleton() {
  return (
    <div className="flex gap-3">
      <Skeleton className="h-3 w-3 rounded-full mt-1" />
      <div className="flex-1 space-y-1">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-32" />
      </div>
    </div>
  )
}
