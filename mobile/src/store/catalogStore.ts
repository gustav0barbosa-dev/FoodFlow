import { create } from 'zustand'
import { useLocationStore } from '@/store/locationStore'

export interface CatalogState {
  restaurants: any[]
  loading: boolean
  error: string | null
  load: () => Promise<void>
}

let inFlight: Promise<void> | null = null

export const useCatalogStore = create<CatalogState>((set, get) => ({
  restaurants: [],
  loading: false,
  error: null,

  load: async () => {
    if (inFlight) return inFlight

    set({ loading: true, error: null })

    inFlight = (async () => {
      try {
        const { searchRestaurants } = await import('@/lib/api')
        const { lat, lon } = useLocationStore.getState()
        const apiRestaurants = await searchRestaurants({ lat, lon })

        const { mapApiRestaurant } = await import('@/lib/catalog')
        const mapped = apiRestaurants.map((item) => mapApiRestaurant(item))

        set({
          restaurants: mapped,
          loading: false,
          error: null,
        })
      } catch {
        const { restaurants } = await import('@/data/mockData')
        set({
          restaurants,
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
