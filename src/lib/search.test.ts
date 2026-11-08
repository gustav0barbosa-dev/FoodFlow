import { describe, expect, it } from 'vitest'
import { restaurants } from '@/data/mockData'
import {
  filterRestaurants,
  getMatchingMenuItems,
  matchesQuery,
  splitHighlight,
} from '@/lib/search'

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

  it('encontra restaurantes por prato do cardápio', () => {
    expect(filterRestaurants(restaurants, 'feijoada').map((r) => r.id)).toEqual([
      'r1',
    ])
    expect(filterRestaurants(restaurants, 'falafel').map((r) => r.id)).toEqual([
      'r8',
      'r12',
    ])
  })

  it('encontra restaurantes por descrição do prato', () => {
    expect(filterRestaurants(restaurants, 'vinagrete').map((r) => r.id)).toEqual([
      'r1',
    ])
    expect(filterRestaurants(restaurants, 'folhado').map((r) => r.id)).toEqual([
      'r7',
    ])
    expect(filterRestaurants(restaurants, 'granola').map((r) => r.id)).toEqual([
      'r2',
      'r6',
    ])
  })

  it('encontra prato ignorando acentos', () => {
    expect(filterRestaurants(restaurants, 'tiramisu').map((r) => r.id)).toEqual([
      'r3',
    ])
    expect(filterRestaurants(restaurants, 'acai').map((r) => r.id)).toEqual([
      'r2',
      'r6',
    ])
  })

  it('encontra descrição ignorando acentos', () => {
    expect(filterRestaurants(restaurants, 'lime').map((r) => r.id)).toEqual([])
    expect(
      filterRestaurants(restaurants, 'granola').map((r) => r.id)
    ).toEqual(['r2', 'r6'])
  })

  it('retorna lista vazia quando não há correspondência', () => {
    expect(filterRestaurants(restaurants, 'comida marciana')).toEqual([])
  })
})

describe('getMatchingMenuItems', () => {
  it('retorna apenas os pratos correspondentes pelo nome', () => {
    const restaurant = restaurants.find((r) => r.id === 'r5')

    expect(restaurant).toBeDefined()
    expect(
      getMatchingMenuItems(restaurant!, 'sashimi').map((item) => item.name)
    ).toEqual([
      'Combinado Kaze (24 peças)',
      'Sashimi de Salmão (10 fatias)',
    ])
  })

  it('retorna pratos correspondentes pela descrição', () => {
    const restaurant = restaurants.find((r) => r.id === 'r1')

    expect(restaurant).toBeDefined()
    expect(
      getMatchingMenuItems(restaurant!, 'vinagrete').map((item) => item.name)
    ).toEqual(['Costela da Vila'])
  })

  it('retorna lista vazia para busca vazia', () => {
    const restaurant = restaurants.find((r) => r.id === 'r1')

    expect(restaurant).toBeDefined()
    expect(getMatchingMenuItems(restaurant!, '  ')).toEqual([])
  })
})

describe('matchesQuery', () => {
  it('corresponde ignorando acentos e caixa', () => {
    expect(matchesQuery('Açaí Bowl', 'acai')).toBe(true)
    expect(matchesQuery('Feijoada Completa', 'FEIJOADA')).toBe(true)
  })

  it('retorna falso quando não há correspondência', () => {
    expect(matchesQuery('Pizza da Praça', 'sushi')).toBe(false)
  })

  it('retorna falso para busca vazia', () => {
    expect(matchesQuery('Qualquer coisa', '   ')).toBe(false)
  })
})

describe('splitHighlight', () => {
  it('separa o trecho correspondente ignorando acentos', () => {
    expect(splitHighlight('Açaí Bowl', 'acai')).toEqual([
      { text: 'Açaí', match: true },
      { text: ' Bowl', match: false },
    ])
  })

  it('destaca todas as ocorrências do termo', () => {
    expect(splitHighlight('Pizza da Praça', 'pizza')).toEqual([
      { text: 'Pizza', match: true },
      { text: ' da Praça', match: false },
    ])
  })

  it('retorna o texto inteiro sem destaque quando a busca está vazia', () => {
    expect(splitHighlight('Açaí Bowl', '   ')).toEqual([
      { text: 'Açaí Bowl', match: false },
    ])
  })
})
