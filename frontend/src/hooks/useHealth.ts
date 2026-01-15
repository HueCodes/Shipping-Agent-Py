import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/client'
import { useUIStore } from '../stores/uiStore'

export function useHealth() {
  const setMockMode = useUIStore((s) => s.setMockMode)

  const query = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
    staleTime: 60_000, // 1 minute
    refetchInterval: 60_000,
  })

  useEffect(() => {
    if (query.data) {
      setMockMode(query.data.mock_mode)
    }
  }, [query.data, setMockMode])

  return query
}
