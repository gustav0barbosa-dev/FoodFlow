import { useEffect, useState } from 'react'
import { useCatalog } from '@/hooks/useCatalog'
import { filterRestaurants } from '@/lib/search'
import type { Restaurant } from '@/types'

const SEARCH_DELAY_MS = 300

interface SearchState {
  results: Restaurant[]
  loading: boolean
  error: string | null
}

export function useRestaurantSearch(query: string) {
  const { restaurants, load } = useCatalog()
  const [state, setState] = useState<SearchState>({
    results: restaurants,
    loading: false,
    error: null,
  })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const term = query.trim()

    if (!term) {
      setState({ results: restaurants, loading: false, error: null })
      return
    }

    setState((current) => ({ ...current, loading: true, error: null }))

    const timeout = setTimeout(() => {
      try {
        const results = filterRestaurants(restaurants, term)
        setState({ results, loading: false, error: null })
      } catch {
        setState({
          results: [],
          loading: false,
          error: 'Não foi possível buscar agora. Tente novamente.',
        })
      }
    }, SEARCH_DELAY_MS)

    return () => clearTimeout(timeout)
  }, [query, attempt, restaurants])

  const retry = () => {
    void load(true)
    setAttempt((value) => value + 1)
  }

  return { ...state, retry }
}
