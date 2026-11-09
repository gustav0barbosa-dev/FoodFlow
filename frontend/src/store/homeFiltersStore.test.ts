import { describe, expect, it } from 'vitest'
import {
  DEFAULT_HOME_CATEGORY,
  DEFAULT_HOME_FILTER,
  useHomeFiltersStore,
} from '@/store/homeFiltersStore'

describe('homeFiltersStore', () => {
  it('inicia com os filtros padrão', () => {
    expect(useHomeFiltersStore.getState().filter).toBe(DEFAULT_HOME_FILTER)
    expect(useHomeFiltersStore.getState().category).toBe(DEFAULT_HOME_CATEGORY)
  })

  it('persiste filtro e categoria em localStorage', () => {
    useHomeFiltersStore.getState().setFilter('Vegano')
    useHomeFiltersStore.getState().setCategory('Saudável')

    const stored = localStorage.getItem('foodflow-home-filters')
    expect(stored).toContain('Vegano')
    expect(stored).toContain('Saudável')
  })

  it('reidrata os filtros salvos', async () => {
    localStorage.setItem(
      'foodflow-home-filters',
      JSON.stringify({
        state: { filter: 'Frete grátis', category: 'Pizza' },
        version: 0,
      })
    )

    await useHomeFiltersStore.persist.rehydrate()

    expect(useHomeFiltersStore.getState().filter).toBe('Frete grátis')
    expect(useHomeFiltersStore.getState().category).toBe('Pizza')
  })

  it('ignora valores inválidos do localStorage', async () => {
    localStorage.setItem(
      'foodflow-home-filters',
      JSON.stringify({ state: { filter: 123, category: 456 }, version: 0 })
    )

    await useHomeFiltersStore.persist.rehydrate()

    expect(useHomeFiltersStore.getState().filter).toBe(DEFAULT_HOME_FILTER)
    expect(useHomeFiltersStore.getState().category).toBe(DEFAULT_HOME_CATEGORY)
  })

  it('restaura os padrões ao resetar filtros', () => {
    useHomeFiltersStore.getState().setFilter('Vegano')
    useHomeFiltersStore.getState().setCategory('Pizza')

    useHomeFiltersStore.getState().resetFilters()

    expect(useHomeFiltersStore.getState().filter).toBe(DEFAULT_HOME_FILTER)
    expect(useHomeFiltersStore.getState().category).toBe(DEFAULT_HOME_CATEGORY)
  })
})
