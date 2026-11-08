import type { AnalyticsEvent, EventType } from '@/store/eventsStore'

export const EVENT_LABELS: Record<EventType, string> = {
  restaurant_card_clicked: 'Card clicado',
  restaurant_opened: 'Restaurante aberto',
  add_to_cart: 'Item adicionado',
  order_completed: 'Pedido concluído',
  preferences_updated: 'Preferências atualizadas',
  search_performed: 'Busca realizada',
  favorite_toggled: 'Favorito alterado',
  order_status_updated: 'Status do pedido atualizado',
  review_submitted: 'Avaliação enviada',
}

export const EVENT_TYPES = Object.keys(EVENT_LABELS) as EventType[]

export type EventPeriod = 'today' | '7d' | '30d' | 'all'

export const EVENT_PERIODS: { value: EventPeriod; label: string }[] = [
  { value: 'today', label: 'Hoje' },
  { value: '7d', label: '7 dias' },
  { value: '30d', label: '30 dias' },
  { value: 'all', label: 'Tudo' },
]

export interface EventFilters {
  type: EventType | 'all'
  period: EventPeriod
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function periodStart(period: EventPeriod, now: Date): Date | null {
  if (period === 'all') return null

  const start = startOfDay(now)
  if (period === 'today') return start

  const days = period === '7d' ? 6 : 29
  start.setDate(start.getDate() - days)
  return start
}

export function filterEvents(
  events: AnalyticsEvent[],
  filters: EventFilters,
  now = new Date()
) {
  const start = periodStart(filters.period, now)

  return events.filter((event) => {
    if (filters.type !== 'all' && event.type !== filters.type) return false
    if (!start) return true
    return new Date(event.createdAt) >= start
  })
}

export interface EventTypeCount {
  type: EventType
  count: number
}

export function countEventsByType(events: AnalyticsEvent[]): EventTypeCount[] {
  const counts = new Map<EventType, number>()

  for (const event of events) {
    counts.set(event.type, (counts.get(event.type) ?? 0) + 1)
  }

  return Array.from(counts, ([type, count]) => ({ type, count })).sort(
    (a, b) =>
      b.count - a.count || EVENT_LABELS[a.type].localeCompare(EVENT_LABELS[b.type])
  )
}
