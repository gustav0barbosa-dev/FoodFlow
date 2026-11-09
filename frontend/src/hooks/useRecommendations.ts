import { useEffect, useState } from 'react'
import { getRecommendations } from '@/lib/api'
import { mapApiRestaurant } from '@/lib/catalog'
import { API_USER_ID, getABGroup, getCurrentTurno } from '@/lib/config'
import { useCatalogStore } from '@/store/catalogStore'
import { useLocationStore } from '@/store/locationStore'
import type { Restaurant } from '@/types'

/**
 * Busca recomendações personalizadas e usa o catálogo local como fallback
 * quando a API está indisponível. Respeita o grupo do experimento A/B
 * (personalized ou distance) definido via VITE_AB_GROUP.
 */
export function useRecommendations(initial: Restaurant[]) {
  const [recommended, setRecommended] = useState<Restaurant[]>(() =>
    initial.filter((restaurant) => restaurant.isRecommended)
  )
  const [loading, setLoading] = useState(true)
  const [experimentGroup, setExperimentGroup] = useState<string | undefined>()
  const lat = useLocationStore((state) => state.lat)
  const lon = useLocationStore((state) => state.lon)
  const setRecommendedIds = useCatalogStore(
    (state) => state.setRecommendedIds
  )

  useEffect(() => {
    const group = getABGroup()
    setExperimentGroup(group || undefined)

    let active = true
    setLoading(true)

    getRecommendations({
      userId: API_USER_ID,
      lat,
      lon,
      turno: getCurrentTurno(),
      experiment: group || undefined,
    })
      .then((items) => {
        if (!active) return
        const mapped = items.map((item) => mapApiRestaurant(item, true))
        setRecommended(mapped)
        setRecommendedIds(mapped.map((restaurant) => restaurant.id))
      })
      .catch(() => {
        if (!active) return
        const fallback = useCatalogStore
          .getState()
          .restaurants.filter((restaurant) => restaurant.isRecommended)
        setRecommended(fallback)
        setRecommendedIds(fallback.map((restaurant) => restaurant.id))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [lat, lon, setRecommendedIds, experimentGroup])

  return { recommended, loading, experimentGroup }
}
