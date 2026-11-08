import { describe, expect, it } from 'vitest'
import { restaurants } from '@/data/mockData'
import { filterRestaurants } from '@/lib/search'

describe('filterRestaurants', () => {
  it('retorna todos os restaurantes para busca vazia', () => {
    expect(filterRestaurants(restaurants, '   ')).toHaveLength(restaurants.length)
  })

  it('encontra por nome ou categoria ignorando acentos e caixa', () => {
    expect(filterRestaurants(restaurants, 'JAPONES').map((r) => r.id)).toEqual([
      'r5',
      'r10',
    ])
    expect(filterRestaurants(restaurants, 'pizza').map((r) => r.id)).toEqual([
      'r3',
      'r11',
    ])
  })

  it('retorna lista vazia quando não há correspondência', () => {
    expect(filterRestaurants(restaurants, 'comida marciana')).toEqual([])
  })
})
