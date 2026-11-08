import { describe, expect, it } from 'vitest'
import { useCartStore } from '@/store/cartStore'
import { useFavoritesStore } from '@/store/favoritesStore'
import { usePreferencesStore } from '@/store/preferencesStore'
import type { MenuItem } from '@/types'

const feijoada: MenuItem = {
  id: 'r1-m1',
  name: 'Feijoada Completa',
  description: 'Serve 2 pessoas',
  price: 42.9,
  image: 'https://example.com/feijoada.jpg',
}

describe('cartStore', () => {
  it('adiciona itens e agrupa quantidades do mesmo item', () => {
    const { addItem } = useCartStore.getState()

    addItem('r1', 'Sabor da Vila', feijoada)
    addItem('r1', 'Sabor da Vila', feijoada)

    const state = useCartStore.getState()
    expect(state.lines).toHaveLength(1)
    expect(state.lines[0].quantity).toBe(2)
    expect(state.count()).toBe(2)
    expect(state.total()).toBeCloseTo(85.8)
  })

  it('incrementa, decrementa e remove ao chegar em zero', () => {
    const { addItem, incrementItem, decrementItem } = useCartStore.getState()

    addItem('r1', 'Sabor da Vila', feijoada)
    incrementItem(feijoada.id)
    expect(useCartStore.getState().lines[0].quantity).toBe(2)

    decrementItem(feijoada.id)
    expect(useCartStore.getState().lines[0].quantity).toBe(1)

    decrementItem(feijoada.id)
    expect(useCartStore.getState().lines).toEqual([])
  })

  it('limpa a sacola', () => {
    const { addItem, clear } = useCartStore.getState()

    addItem('r1', 'Sabor da Vila', feijoada)
    clear()

    expect(useCartStore.getState().lines).toEqual([])
    expect(useCartStore.getState().count()).toBe(0)
  })
})

describe('favoritesStore', () => {
  it('alterna favoritos sem duplicar', () => {
    const { toggleFavorite } = useFavoritesStore.getState()

    toggleFavorite('r1')
    toggleFavorite('r2')
    expect(useFavoritesStore.getState().favoriteIds).toEqual(['r1', 'r2'])

    toggleFavorite('r1')
    expect(useFavoritesStore.getState().favoriteIds).toEqual(['r2'])
  })

  it('persiste a lista em localStorage', () => {
    useFavoritesStore.getState().toggleFavorite('r3')

    const stored = localStorage.getItem('foodflow-favorites')
    expect(stored).toContain('r3')
  })
})

describe('preferencesStore', () => {
  it('adiciona, remove e limpa preferências', () => {
    const { togglePreference, clearPreferences } = usePreferencesStore.getState()

    togglePreference('Vegano')
    togglePreference('Sem glúten')
    expect(usePreferencesStore.getState().preferences).toEqual([
      'Vegano',
      'Sem glúten',
    ])

    togglePreference('Vegano')
    expect(usePreferencesStore.getState().preferences).toEqual(['Sem glúten'])

    clearPreferences()
    expect(usePreferencesStore.getState().preferences).toEqual([])
  })
})
