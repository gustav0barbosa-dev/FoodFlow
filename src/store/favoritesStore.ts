import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface FavoritesState {
  favoriteIds: string[]
  toggleFavorite: (restaurantId: string) => void
}

export const useFavoritesStore = create<FavoritesState>()(
  persist(
    (set, get) => ({
      favoriteIds: [],

      toggleFavorite: (restaurantId) =>
        set({
          favoriteIds: get().favoriteIds.includes(restaurantId)
            ? get().favoriteIds.filter((id) => id !== restaurantId)
            : [...get().favoriteIds, restaurantId],
        }),
    }),
    {
      name: 'foodflow-favorites',
      partialize: (state) => ({ favoriteIds: state.favoriteIds }),
    }
  )
)
