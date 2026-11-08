import { describe, expect, it } from 'vitest'
import {
  DEFAULT_HOME_SEARCH_QUERY,
  useHomeSearchStore,
} from '@/store/homeSearchStore'

describe('homeSearchStore', () => {
  it('inicia com a busca vazia', () => {
    expect(useHomeSearchStore.getState().query).toBe(DEFAULT_HOME_SEARCH_QUERY)
  })

  it('persiste a query em localStorage', () => {
    useHomeSearchStore.getState().setQuery('pizza')

    expect(localStorage.getItem('foodflow-home-search')).toContain('pizza')
  })

  it('reidrata a query salva', async () => {
    localStorage.setItem(
      'foodflow-home-search',
      JSON.stringify({ state: { query: 'sushi' }, version: 0 })
    )

    await useHomeSearchStore.persist.rehydrate()

    expect(useHomeSearchStore.getState().query).toBe('sushi')
  })
})
