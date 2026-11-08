import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { restaurants } from '@/data/mockData'
import { useRestaurantSearch } from '@/hooks/useRestaurantSearch'

describe('useRestaurantSearch', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('começa com todos os restaurantes e sem carregamento', () => {
    const { result } = renderHook(() => useRestaurantSearch(''))

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(result.current.results).toHaveLength(restaurants.length)
  })

  it('carrega e filtra após o debounce', async () => {
    const { result, rerender } = renderHook(
      ({ query }: { query: string }) => useRestaurantSearch(query),
      { initialProps: { query: '' } }
    )

    rerender({ query: 'pizza' })
    expect(result.current.loading).toBe(true)

    await act(async () => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.results.map((r) => r.id)).toEqual(['r3', 'r11'])
  })

  it('volta à lista completa ao limpar a busca', async () => {
    const { result, rerender } = renderHook(
      ({ query }: { query: string }) => useRestaurantSearch(query),
      { initialProps: { query: 'pizza' } }
    )

    await act(async () => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current.results).toHaveLength(2)

    rerender({ query: '' })
    expect(result.current.loading).toBe(false)
    expect(result.current.results).toHaveLength(restaurants.length)
  })
})
