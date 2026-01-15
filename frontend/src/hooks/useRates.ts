import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import type { RateRequest, Rate } from '../api/types'

export function useRates() {
  return useMutation({
    mutationFn: (params: RateRequest) => api.getRates(params),
  })
}

// Helper to find best value and fastest options
export function analyzeRates(rates: Rate[]) {
  if (rates.length === 0) return { bestValue: null, fastest: null }

  // Best value = cheapest
  const bestValue = rates.reduce((min, rate) =>
    rate.price < min.price ? rate : min
  )

  // Fastest = lowest delivery_days (excluding null)
  const withDelivery = rates.filter((r) => r.delivery_days !== null)
  const fastest =
    withDelivery.length > 0
      ? withDelivery.reduce((min, rate) =>
          (rate.delivery_days ?? Infinity) < (min.delivery_days ?? Infinity)
            ? rate
            : min
        )
      : null

  return { bestValue, fastest }
}

// Sort rates by different criteria
export function sortRates(
  rates: Rate[],
  sortBy: 'price' | 'delivery' | 'carrier' = 'price'
): Rate[] {
  const sorted = [...rates]

  switch (sortBy) {
    case 'price':
      return sorted.sort((a, b) => a.price - b.price)
    case 'delivery':
      return sorted.sort((a, b) => {
        const aDelivery = a.delivery_days ?? Infinity
        const bDelivery = b.delivery_days ?? Infinity
        return aDelivery - bDelivery
      })
    case 'carrier':
      return sorted.sort((a, b) => a.carrier.localeCompare(b.carrier))
    default:
      return sorted
  }
}
