import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Order } from '../api/types'

interface OrderFilters {
  limit?: number
  status?: string
  search?: string
}

export function useOrders(filters?: OrderFilters) {
  return useQuery({
    queryKey: ['orders', filters],
    queryFn: () => api.getOrders(filters),
    staleTime: 30_000, // 30 seconds
    refetchOnWindowFocus: true,
  })
}

export function useOrder(orderId: string | null) {
  return useQuery({
    queryKey: ['order', orderId],
    queryFn: () => api.getOrder(orderId!),
    enabled: !!orderId,
    staleTime: 60_000, // 1 minute
  })
}

export function useSyncOrders() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ status, limit }: { status?: string; limit?: number } = {}) =>
      api.syncOrders(status, limit),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}

export function useFulfillOrder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (orderId: string) => api.fulfillOrder(orderId),
    onSuccess: (_, orderId) => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      queryClient.invalidateQueries({ queryKey: ['order', orderId] })
    },
  })
}
