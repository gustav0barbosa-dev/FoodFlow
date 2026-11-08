import { describe, expect, it } from 'vitest'
import type { Restaurant } from '@/types'
import { isRestaurantSort, sortRestaurants } from '@/lib/sort'

function buildRestaurant(overrides: Partial<Restaurant>): Restaurant {
  return {
    id: 'r1',
    name: 'Restaurante',
    category: 'Brasileira',
    image: 'https://example.com/img.jpg',
    rating: 4.5,
    reviewCount: 10,
    distanceKm: 1,
    deliveryFee: 5,
    deliveryTimeMin: 20,
    deliveryTimeMax: 30,
    address: 'Rua A, 1',
    phone: '11 99999-0000',
    tags: [],
    dietaryTags: [],
    isRecommended: false,
    menu: [],
    reviews: [],
    hours: 'Seg a Sex: 09h–18h',
    paymentMethods: ['Cartão', 'Pix'],
    ...overrides,
  }
}

describe('sortRestaurants', () => {
  it('mantém a ordem original em recomendados', () => {
    const restaurants = [
      buildRestaurant({ id: 'a', name: 'A' }),
      buildRestaurant({ id: 'b', name: 'B' }),
    ]

    expect(sortRestaurants(restaurants, 'recommended')).toBe(restaurants)
  })

  it('ordena por avaliação e desempata pelo nome', () => {
    const restaurants = [
      buildRestaurant({ id: 'a', name: 'Zeta', rating: 4.7 }),
      buildRestaurant({ id: 'b', name: 'Alfa', rating: 4.9 }),
      buildRestaurant({ id: 'c', name: 'Beta', rating: 4.7 }),
    ]

    expect(sortRestaurants(restaurants, 'rating').map((r) => r.id)).toEqual([
      'b',
      'c',
      'a',
    ])
  })

  it('ordena por menor frete e desempata pela avaliação', () => {
    const restaurants = [
      buildRestaurant({ id: 'a', name: 'A', deliveryFee: 7, rating: 4.9 }),
      buildRestaurant({ id: 'b', name: 'B', deliveryFee: 0, rating: 4.2 }),
      buildRestaurant({ id: 'c', name: 'C', deliveryFee: 0, rating: 4.6 }),
    ]

    expect(sortRestaurants(restaurants, 'deliveryFee').map((r) => r.id)).toEqual([
      'c',
      'b',
      'a',
    ])
  })

  it('ordena por menor distância sem alterar o array original', () => {
    const restaurants = [
      buildRestaurant({ id: 'a', name: 'A', distanceKm: 2.4 }),
      buildRestaurant({ id: 'b', name: 'B', distanceKm: 0.8 }),
    ]

    const sorted = sortRestaurants(restaurants, 'distance')

    expect(sorted.map((r) => r.id)).toEqual(['b', 'a'])
    expect(restaurants.map((r) => r.id)).toEqual(['a', 'b'])
  })

  it('valida as opções de ordenação', () => {
    expect(isRestaurantSort('rating')).toBe(true)
    expect(isRestaurantSort('invalido')).toBe(false)
    expect(isRestaurantSort(null)).toBe(false)
  })
})
