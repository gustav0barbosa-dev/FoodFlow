import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface FavoritesState {
  favoriteIds: string[]
  toggleFavorite: (restaurantId: string) => void
  migrateFavoriteIds: (mapping: Map<string, string>) => void
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

      migrateFavoriteIds: (mapping) => {
        const current = get().favoriteIds
        const migrated = [
          ...new Set(current.map((id) => mapping.get(id) ?? id)),
        ]
        const changed =
          migrated.length !== current.length ||
          migrated.some((id, index) => id !== current[index])

        if (changed) set({ favoriteIds: migrated })
      },
    }),
    {
      name: 'foodflow-favorites',
      partialize: (state) => ({ favoriteIds: state.favoriteIds }),
    }
  )
)
