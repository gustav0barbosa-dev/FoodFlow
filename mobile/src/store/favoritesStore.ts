import { create } from 'zustand'

export interface FavoritesState {
  favoriteIds: string[]
  toggleFavorite: (restaurantId: string) => void
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  favoriteIds: [],

  toggleFavorite: (restaurantId) =>
    set({
      favoriteIds: get().favoriteIds.includes(restaurantId)
        ? get().favoriteIds.filter((id) => id !== restaurantId)
        : [...get().favoriteIds, restaurantId],
    }),
}))
