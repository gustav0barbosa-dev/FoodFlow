import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const DEFAULT_HOME_FILTER = 'Todos'
export const DEFAULT_HOME_CATEGORY: string | null = null

interface HomeFiltersState {
  filter: string
  category: string | null
  setFilter: (filter: string) => void
  setCategory: (category: string | null) => void
  resetFilters: () => void
}

export const useHomeFiltersStore = create<HomeFiltersState>()(
  persist(
    (set) => ({
      filter: DEFAULT_HOME_FILTER,
      category: DEFAULT_HOME_CATEGORY,

      setFilter: (filter) => set({ filter }),
      setCategory: (category) => set({ category }),
      resetFilters: () =>
        set({ filter: DEFAULT_HOME_FILTER, category: DEFAULT_HOME_CATEGORY }),
    }),
    {
      name: 'foodflow-home-filters',
      partialize: (state) => ({
        filter: state.filter,
        category: state.category,
      }),
      merge: (persisted, current) => {
        const stored = persisted as {
          filter?: unknown
          category?: unknown
        } | undefined

        return {
          ...current,
          filter:
            typeof stored?.filter === 'string'
              ? stored.filter
              : current.filter,
          category:
            stored?.category === null ||
            typeof stored?.category === 'string'
              ? stored.category
              : current.category,
        }
      },
    }
  )
)
