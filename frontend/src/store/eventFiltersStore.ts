import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { EventType } from '@/store/eventsStore'
import type { EventPeriod } from '@/lib/events'

export const DEFAULT_EVENT_TYPE: EventType | 'all' = 'all'
export const DEFAULT_EVENT_PERIOD: EventPeriod = 'all'

interface EventFiltersState {
  type: EventType | 'all'
  period: EventPeriod
  setType: (type: EventType | 'all') => void
  setPeriod: (period: EventPeriod) => void
  resetFilters: () => void
}

export const useEventFiltersStore = create<EventFiltersState>()(
  persist(
    (set) => ({
      type: DEFAULT_EVENT_TYPE,
      period: DEFAULT_EVENT_PERIOD,

      setType: (type) => set({ type }),
      setPeriod: (period) => set({ period }),
      resetFilters: () => set({ type: DEFAULT_EVENT_TYPE, period: DEFAULT_EVENT_PERIOD }),
    }),
    {
      name: 'foodflow-event-filters',
      partialize: (state) => ({ type: state.type, period: state.period }),
    }
  )
)
