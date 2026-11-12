import { useEffect, useState } from 'react'
import { ApiError, searchNearbyRestaurants } from '@/lib/api'
import { useLocationStore } from '@/store/locationStore'
import type { NearbyCategory, OsmRestaurant } from '@/types'

export const DEFAULT_NEARBY_RADIUS_METERS = 3000

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return 'Serviço de restaurantes do OpenStreetMap ocupado. Tente novamente em instantes.'
    }
    if (error.status === 504) {
      return 'A consulta ao OpenStreetMap demorou demais. Tente novamente.'
    }
    if (error.status === 502) {
      return 'Não foi possível consultar o OpenStreetMap agora.'
    }
    if (error.message) return error.message
  }

  if (error instanceof Error && error.message) return error.message
  return 'Não foi possível buscar restaurantes no OpenStreetMap.'
}

/**
 * Busca restaurantes reais próximos à localização atual via backend.
 *
 * É uma camada de descoberta independente do catálogo do FoodFlow: qualquer
 * falha (Overpass indisponível, rate limit, rede) resulta em lista vazia e
 * mensagem amigável, sem afetar o catálogo próprio.
 */
export function useNearbyRestaurants({
  radius = DEFAULT_NEARBY_RADIUS_METERS,
  category,
}: {
  radius?: number
  category?: NearbyCategory
} = {}) {
  const lat = useLocationStore((state) => state.lat)
  const lon = useLocationStore((state) => state.lon)
  const [restaurants, setRestaurants] = useState<OsmRestaurant[]>([])
  const [source, setSource] = useState('OpenStreetMap')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    searchNearbyRestaurants({ lat, lon, radius, category })
      .then((response) => {
        if (!active) return
        setRestaurants(response.restaurants)
        setSource(response.source)
      })
      .catch((err: unknown) => {
        if (!active) return
        // Evita exibir resultados de outra região após uma falha.
        setRestaurants([])
        setError(friendlyError(err))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [lat, lon, radius, category])

  return { restaurants, loading, error, source }
}
