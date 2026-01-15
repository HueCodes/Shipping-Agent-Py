import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useTracking(shipmentId: string | null) {
  return useQuery({
    queryKey: ['tracking', shipmentId],
    queryFn: () => api.getTracking(shipmentId!),
    enabled: !!shipmentId,
    staleTime: 60_000, // 1 minute - tracking doesn't change that fast
    refetchInterval: 5 * 60_000, // Refetch every 5 minutes when visible
  })
}

// Get status category for styling
export function getStatusCategory(
  status: string
): 'pending' | 'transit' | 'delivered' | 'exception' {
  const lower = status.toLowerCase()

  if (lower.includes('delivered')) return 'delivered'
  if (lower.includes('exception') || lower.includes('failed') || lower.includes('error')) {
    return 'exception'
  }
  if (
    lower.includes('transit') ||
    lower.includes('out_for_delivery') ||
    lower.includes('shipped')
  ) {
    return 'transit'
  }
  return 'pending'
}
