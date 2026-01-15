import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { CreateShipmentRequest } from '../api/types'

export function useShipment(shipmentId: string | null) {
  return useQuery({
    queryKey: ['shipment', shipmentId],
    queryFn: () => api.getShipment(shipmentId!),
    enabled: !!shipmentId,
    staleTime: 60_000,
  })
}

export function useCreateShipment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (params: CreateShipmentRequest) => api.createShipment(params),
    onSuccess: () => {
      // Invalidate orders to reflect updated status
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })
}
