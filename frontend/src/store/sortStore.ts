import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { isRestaurantSort, type RestaurantSort } from '@/lib/sort'

export const DEFAULT_RESTAURANT_SORT: RestaurantSort = 'recommended'

interface SortState {
  sort: RestaurantSort
  setSort: (sort: RestaurantSort) => void
}

export const useSortStore = create<SortState>()(
  persist(
    (set) => ({
      sort: DEFAULT_RESTAURANT_SORT,
      setSort: (sort) => set({ sort }),
    }),
    {
      name: 'foodflow-home-sort',
      partialize: (state) => ({ sort: state.sort }),
      merge: (persisted, current) => {
        const stored = (persisted as { sort?: unknown } | undefined)?.sort

        return {
          ...current,
          sort: isRestaurantSort(stored) ? stored : current.sort,
        }
      },
    }
  )
)
