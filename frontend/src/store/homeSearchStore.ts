import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const DEFAULT_HOME_SEARCH_QUERY = ''

interface HomeSearchState {
  query: string
  setQuery: (query: string) => void
}

export const useHomeSearchStore = create<HomeSearchState>()(
  persist(
    (set) => ({
      query: DEFAULT_HOME_SEARCH_QUERY,
      setQuery: (query) => set({ query }),
    }),
    {
      name: 'foodflow-home-search',
      partialize: (state) => ({ query: state.query }),
    }
  )
)
