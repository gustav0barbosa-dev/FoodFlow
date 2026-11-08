import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type EventType =
  | 'restaurant_card_clicked'
  | 'restaurant_opened'
  | 'add_to_cart'
  | 'order_completed'
  | 'preferences_updated'
  | 'search_performed'

export type EventPayload = Record<string, string | number | string[]>

export interface AnalyticsEvent {
  id: string
  type: EventType
  payload: EventPayload
  createdAt: string
}

const MAX_EVENTS = 50

interface EventsState {
  events: AnalyticsEvent[]
  trackEvent: (type: EventType, payload?: EventPayload) => void
  clearEvents: () => void
}

export const useEventsStore = create<EventsState>()(
  persist(
    (set, get) => ({
      events: [],

      trackEvent: (type, payload = {}) => {
        const event: AnalyticsEvent = {
          id: `e${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type,
          payload,
          createdAt: new Date().toISOString(),
        }

        // Mock transport: with a backend, this event would be sent via POST /events.
        set({ events: [event, ...get().events].slice(0, MAX_EVENTS) })
      },

      clearEvents: () => set({ events: [] }),
    }),
    {
      name: 'foodflow-events',
      partialize: (state) => ({ events: state.events }),
    }
  )
)
