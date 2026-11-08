import { describe, expect, it } from 'vitest'
import { DEFAULT_RESTAURANT_SORT, useSortStore } from '@/store/sortStore'

describe('sortStore', () => {
  it('inicia com a ordenação recomendada', () => {
    expect(useSortStore.getState().sort).toBe(DEFAULT_RESTAURANT_SORT)
  })

  it('persiste a ordenação escolhida em localStorage', () => {
    useSortStore.getState().setSort('distance')

    expect(localStorage.getItem('foodflow-home-sort')).toContain('distance')
  })

  it('reidrata a ordenação salva', async () => {
    localStorage.setItem(
      'foodflow-home-sort',
      JSON.stringify({ state: { sort: 'rating' }, version: 0 })
    )

    await useSortStore.persist.rehydrate()

    expect(useSortStore.getState().sort).toBe('rating')
  })

  it('ignora um valor inválido vindo do localStorage', async () => {
    localStorage.setItem(
      'foodflow-home-sort',
      JSON.stringify({ state: { sort: 'invalido' }, version: 0 })
    )

    await useSortStore.persist.rehydrate()

    expect(useSortStore.getState().sort).toBe(DEFAULT_RESTAURANT_SORT)
  })
})
