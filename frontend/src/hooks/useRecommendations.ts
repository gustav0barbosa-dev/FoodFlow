import { useEffect, useState } from 'react'
import { getRecommendations } from '@/lib/api'
import { mapApiRestaurant } from '@/lib/catalog'
import { API_USER_ID, getCurrentTurno } from '@/lib/config'
import { useABGroupStore } from '@/store/abGroupStore'
import { useCatalogStore } from '@/store/catalogStore'
import { useLocationStore } from '@/store/locationStore'
import type { Restaurant } from '@/types'

/**
 * Busca recomendações personalizadas e usa o catálogo local como fallback
 * quando a API está indisponível.
 *
 * O modo vem de ``abGroupStore``:
 * - ``experiment``: o backend usa a atribuição persistente do usuário e ignora
 *   qualquer seleção manual;
 * - ``demo``: a estratégia escolhida é enviada explicitamente e os eventos são
 *   marcados como demonstração.
 *
 * O contexto efetivo (grupo, modo, versão, recommendation_id e posições) é
 * guardado no catálogo para que impressões, cliques e compras sejam atribuídos
 * à exposição correta.
 */
export function useRecommendations(initial: Restaurant[]) {
  const [recommended, setRecommended] = useState<Restaurant[]>(() =>
    initial.filter((restaurant) => restaurant.isRecommended)
  )
  const [loading, setLoading] = useState(true)
  const [experimentGroup, setExperimentGroup] = useState<string | undefined>()
  const [modelVersion, setModelVersion] = useState<string | undefined>()
  const [strategy, setStrategy] = useState<string | undefined>()
  const lat = useLocationStore((state) => state.lat)
  const lon = useLocationStore((state) => state.lon)
  const setRecommendedIds = useCatalogStore(
    (state) => state.setRecommendedIds
  )
  const setRecommendationContext = useCatalogStore(
    (state) => state.setRecommendationContext
  )
  const selectedGroup = useABGroupStore((state) => state.group)
  const mode = useABGroupStore((state) => state.mode)

  useEffect(() => {
    let active = true
    setLoading(true)

    getRecommendations({
      userId: API_USER_ID,
      lat,
      lon,
      turno: getCurrentTurno(),
      mode,
      experiment: mode === 'demo' ? selectedGroup || undefined : undefined,
    })
      .then((result) => {
        if (!active) return
        const mapped = result.recommendations.map((item) =>
          mapApiRestaurant(item, true)
        )
        const positions = Object.fromEntries(
          mapped.map((restaurant, index) => [restaurant.id, index])
        )

        setRecommended(mapped)
        setRecommendedIds(mapped.map((restaurant) => restaurant.id))
        setExperimentGroup(result.experimentGroup || undefined)
        setModelVersion(result.modelVersion || undefined)
        setStrategy(result.strategy || undefined)
        setRecommendationContext({
          experimentGroup: result.experimentGroup,
          experimentMode: result.experimentMode,
          experimentVersion: result.experimentVersion,
          recommendationId: result.recommendationId,
          modelVersion: result.modelVersion,
          strategy: result.strategy,
          positions,
        })
      })
      .catch(() => {
        if (!active) return
        const fallback = useCatalogStore
          .getState()
          .restaurants.filter((restaurant) => restaurant.isRecommended)
        setRecommended(fallback)
        setRecommendedIds(fallback.map((restaurant) => restaurant.id))
        setRecommendationContext(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [
    lat,
    lon,
    mode,
    setRecommendedIds,
    setRecommendationContext,
    selectedGroup,
  ])

  return { recommended, loading, experimentGroup, modelVersion, strategy }
}
