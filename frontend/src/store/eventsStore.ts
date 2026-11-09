import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { sendEvent } from '@/lib/api'

export type EventType =
  | 'restaurant_card_clicked'
  | 'restaurant_opened'
  | 'add_to_cart'
  | 'order_completed'
  | 'preferences_updated'
  | 'search_performed'
  | 'favorite_toggled'
  | 'order_status_updated'
  | 'review_submitted'

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

        // O histórico local continua disponível; a API recebe uma cópia.
        set({ events: [event, ...get().events].slice(0, MAX_EVENTS) })

        void sendEvent(type, payload).catch(() => {
          // Eventos são best-effort; a UI não deve bloquear sem API.
        })
      },

      clearEvents: () => set({ events: [] }),
    }),
    {
      name: 'foodflow-events',
      partialize: (state) => ({ events: state.events }),
    }
  )
)
