import { describe, expect, it } from 'vitest'
import {
  DEFAULT_EVENT_PERIOD,
  DEFAULT_EVENT_TYPE,
  useEventFiltersStore,
} from '@/store/eventFiltersStore'

describe('eventFiltersStore', () => {
  it('inicia com os filtros padrão', () => {
    expect(useEventFiltersStore.getState().type).toBe(DEFAULT_EVENT_TYPE)
    expect(useEventFiltersStore.getState().period).toBe(DEFAULT_EVENT_PERIOD)
  })

  it('persiste tipo e período em localStorage', () => {
    useEventFiltersStore.getState().setType('add_to_cart')
    useEventFiltersStore.getState().setPeriod('7d')

    const stored = localStorage.getItem('foodflow-event-filters')
    expect(stored).toContain('add_to_cart')
    expect(stored).toContain('7d')
  })

  it('reidrata os filtros salvos', async () => {
    localStorage.setItem(
      'foodflow-event-filters',
      JSON.stringify({
        state: { type: 'search_performed', period: '30d' },
        version: 0,
      })
    )

    await useEventFiltersStore.persist.rehydrate()

    expect(useEventFiltersStore.getState().type).toBe('search_performed')
    expect(useEventFiltersStore.getState().period).toBe('30d')
  })

  it('restaura os padrões ao limpar filtros', () => {
    useEventFiltersStore.getState().setType('order_completed')
    useEventFiltersStore.getState().setPeriod('today')

    useEventFiltersStore.getState().resetFilters()

    expect(useEventFiltersStore.getState().type).toBe('all')
    expect(useEventFiltersStore.getState().period).toBe('all')
  })
})
