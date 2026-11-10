import { create } from 'zustand'
import { useLocationStore } from '@/store/locationStore'

export interface CatalogState {
  restaurants: any[]
  recommended: any[]
  loading: boolean
  error: string | null
  load: () => Promise<void>
}

let inFlight: Promise<void> | null = null

export const useCatalogStore = create<CatalogState>((set) => ({
  restaurants: [],
  recommended: [],
  loading: false,
  error: null,

  load: async () => {
    if (inFlight) return inFlight

    set({ loading: true, error: null })

    inFlight = (async () => {
      try {
        const [{ searchRestaurants }, { mapApiRestaurant }] =
          await Promise.all([import('@/lib/api'), import('@/lib/catalog')])
        const { lat, lon } = useLocationStore.getState()

        // As recomendações começam em paralelo, mas não bloqueiam o
        // catálogo: se o endpoint falhar, a home já está utilizável.
        const recommendationsPromise = loadRecommendations({ lat, lon })
          .then((items) => ({ items, error: null as string | null }))
          .catch(() => ({
            items: [],
            error: 'Recomendações indisponíveis; exibindo catálogo.',
          }))

        const apiRestaurants = await searchRestaurants({ lat, lon })
        const mapped = apiRestaurants.map((item) => mapApiRestaurant(item))

        set({
          restaurants: mapped,
          recommended: mapped.slice(0, 6),
          loading: false,
          error: null,
        })

        const { items: recommendations, error } = await recommendationsPromise
        const recommendedIds = new Set(
          recommendations.map((restaurant) => restaurant.id)
        )

        const merged = mapped.map((item) =>
          recommendedIds.has(item.id)
            ? { ...item, isRecommended: true }
            : item
        )
        const markedRecommended = merged.filter((item) => item.isRecommended)
        const recommended = recommendations.length
          ? recommendations.map((item) => mapApiRestaurant(item, true))
          : markedRecommended.length
            ? markedRecommended
            : // Fallback: mantém a seção preenchida com o catálogo quando o
              // endpoint de recomendações está indisponível.
              merged.slice(0, 6)

        // Recomendações podem incluir restaurantes fora do raio padrão da
        // busca; garante que todos apareçam no catálogo da home.
        const knownIds = new Set(merged.map((item) => item.id))
        for (const item of recommended) {
          if (!knownIds.has(item.id)) {
            merged.push(item)
            knownIds.add(item.id)
          }
        }

        set({ restaurants: merged, recommended, loading: false, error })
      } catch {
        const { restaurants } = await import('@/data/mockData')
        set({
          restaurants,
          recommended: restaurants.filter((item: any) => item.isRecommended),
          loading: false,
          error: 'API indisponível; usando catálogo local.',
        })
      } finally {
        inFlight = null
      }
    })()

    return inFlight
  },
}))

async function loadRecommendations({ lat, lon }: { lat: number; lon: number }) {
  const { getRecommendations } = await import('@/lib/api')
  const { DEFAULT_USER_ID, getABGroup, getCurrentTurno, isUuid } = await import(
    '@/lib/config'
  )

  if (!isUuid(DEFAULT_USER_ID)) return []

  const abGroup = getABGroup()

  return getRecommendations({
    userId: DEFAULT_USER_ID,
    lat,
    lon,
    turno: getCurrentTurno(),
    experiment: abGroup || undefined,
  })
}
