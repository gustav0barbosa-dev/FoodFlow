import { describe, expect, it } from 'vitest'
import type { AnalyticsEvent } from '@/store/eventsStore'
import { countEventsByType, filterEvents } from '@/lib/events'

const now = new Date('2026-11-08T12:00:00')

function buildEvent(overrides: Partial<AnalyticsEvent>): AnalyticsEvent {
  return {
    id: 'e1',
    type: 'search_performed',
    payload: {},
    createdAt: now.toISOString(),
    ...overrides,
  }
}

const events: AnalyticsEvent[] = [
  buildEvent({ id: 'e1', createdAt: '2026-11-08T09:00:00' }),
  buildEvent({ id: 'e2', type: 'add_to_cart', createdAt: '2026-11-05T09:00:00' }),
  buildEvent({ id: 'e3', type: 'add_to_cart', createdAt: '2026-10-29T09:00:00' }),
  buildEvent({ id: 'e4', type: 'order_completed', createdAt: '2026-09-29T09:00:00' }),
]

describe('filterEvents', () => {
  it('filtra por período a partir do início do dia', () => {
    expect(
      filterEvents(events, { type: 'all', period: 'today' }, now).map((e) => e.id)
    ).toEqual(['e1'])
    expect(
      filterEvents(events, { type: 'all', period: '7d' }, now).map((e) => e.id)
    ).toEqual(['e1', 'e2'])
    expect(
      filterEvents(events, { type: 'all', period: '30d' }, now).map((e) => e.id)
    ).toEqual(['e1', 'e2', 'e3'])
    expect(filterEvents(events, { type: 'all', period: 'all' }, now)).toHaveLength(4)
  })

  it('combina período e tipo', () => {
    expect(
      filterEvents(events, { type: 'add_to_cart', period: '7d' }, now).map((e) => e.id)
    ).toEqual(['e2'])
  })
})

describe('countEventsByType', () => {
  it('conta por tipo e ordena do mais frequente ao menos frequente', () => {
    const counts = countEventsByType(events)

    expect(counts).toEqual([
      { type: 'add_to_cart', count: 2 },
      { type: 'search_performed', count: 1 },
      { type: 'order_completed', count: 1 },
    ])
  })
})
