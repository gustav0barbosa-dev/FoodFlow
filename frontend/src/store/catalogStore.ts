import { create } from 'zustand'
import { restaurants as mockRestaurants } from '@/data/mockData'
import { searchRestaurants } from '@/lib/api'
import { buildLegacyIdMap, mapApiRestaurant } from '@/lib/catalog'
import { useFavoritesStore } from '@/store/favoritesStore'
import { useLocationStore } from '@/store/locationStore'
import type { ExperimentMode } from '@/lib/config'
import type { Restaurant } from '@/types'

export type CatalogSource = 'api' | 'mock'

/**
 * Contexto da última chamada de recomendações. Guarda o grupo do experimento,
 * o modo, a versão do experimento/modelo, o identificador da exposição e a
 * posição de cada restaurante no ranking. Sem esses campos, um clique não pode
 * ser atribuído à exposição que o originou.
 */
export interface RecommendationContext {
  experimentGroup: string
  experimentMode: ExperimentMode
  experimentVersion: string
  recommendationId: string
  modelVersion: string
  strategy: string
  positions: Record<string, number>
}

interface CatalogState {
  restaurants: Restaurant[]
  source: CatalogSource
  loading: boolean
  loaded: boolean
  error: string | null
  recommendedIds: string[]
  recommendationContext: RecommendationContext | null
  load: (force?: boolean) => Promise<void>
  setRecommendedIds: (ids: string[]) => void
  setRecommendationContext: (context: RecommendationContext | null) => void
}

let inFlight: Promise<void> | null = null

export const useCatalogStore = create<CatalogState>()((set, get) => ({
  restaurants: mockRestaurants,
  source: 'mock',
  loading: false,
  loaded: false,
  error: null,
  recommendedIds: [],
  recommendationContext: null,

  load: async (force = false) => {
    if (inFlight) return inFlight
    if (!force && get().loaded) return

    set({ loading: true, error: null })

    inFlight = (async () => {
      try {
        const { lat, lon } = useLocationStore.getState()
        const apiRestaurants = await searchRestaurants({ lat, lon })
        const mapped = apiRestaurants.map((item) => mapApiRestaurant(item))

        useFavoritesStore
          .getState()
          .migrateFavoriteIds(buildLegacyIdMap(apiRestaurants))

        set({
          restaurants: mapped,
          source: 'api',
          loading: false,
          loaded: true,
          error: null,
        })
      } catch {
        set({
          restaurants: mockRestaurants,
          source: 'mock',
          loading: false,
          loaded: true,
          error: 'API indisponível; usando catálogo local.',
        })
      } finally {
        inFlight = null
      }
    })()

    return inFlight
  },

  setRecommendedIds: (ids) => set({ recommendedIds: ids }),
  setRecommendationContext: (context) =>
    set({ recommendationContext: context }),
}))

export function resetCatalogStore() {
  useCatalogStore.setState({
    restaurants: mockRestaurants,
    source: 'mock',
    loading: false,
    loaded: false,
    error: null,
    recommendedIds: [],
    recommendationContext: null,
  })
}
