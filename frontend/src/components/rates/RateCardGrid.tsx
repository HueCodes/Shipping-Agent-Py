import { useState } from 'react'
import { ArrowUpDown } from 'lucide-react'
import { RateCard } from './RateCard'
import { Button } from '../ui'
import { analyzeRates, sortRates } from '../../hooks/useRates'
import type { Rate } from '../../api/types'

type SortOption = 'price' | 'delivery' | 'carrier'

interface RateCardGridProps {
  rates: Rate[]
  selectedRateId?: string
  onSelectRate?: (rateId: string) => void
}

export function RateCardGrid({
  rates,
  selectedRateId,
  onSelectRate,
}: RateCardGridProps) {
  const [sortBy, setSortBy] = useState<SortOption>('price')

  const { bestValue, fastest } = analyzeRates(rates)
  const sortedRates = sortRates(rates, sortBy)

  const sortOptions: { value: SortOption; label: string }[] = [
    { value: 'price', label: 'Price' },
    { value: 'delivery', label: 'Speed' },
    { value: 'carrier', label: 'Carrier' },
  ]

  return (
    <div>
      {/* Sort controls */}
      <div className="flex items-center gap-2 mb-4">
        <ArrowUpDown className="h-4 w-4 text-text-dim" />
        <span className="text-sm text-text-muted">Sort by:</span>
        <div className="flex gap-1">
          {sortOptions.map((option) => (
            <Button
              key={option.value}
              variant={sortBy === option.value ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setSortBy(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Rate cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {sortedRates.map((rate) => (
          <RateCard
            key={rate.rate_id}
            rate={rate}
            isSelected={selectedRateId === rate.rate_id}
            isBestValue={bestValue?.rate_id === rate.rate_id}
            isFastest={fastest?.rate_id === rate.rate_id && fastest?.rate_id !== bestValue?.rate_id}
            onSelect={onSelectRate}
          />
        ))}
      </div>

      {rates.length === 0 && (
        <div className="text-center text-text-dim py-8">
          No rates available
        </div>
      )}
    </div>
  )
}
