import { describe, expect, it } from 'vitest'
import {
  mapApiReview,
  mapApiRestaurant,
  mapApiRestaurantDetail,
  buildLegacyIdMap,
} from '@/lib/catalog'
import type { ApiRestaurant, ApiReview } from '@/lib/api'

const apiRestaurant: ApiRestaurant = {
  id: 'api-uuid-1',
  name: 'Sabor da Vila',
  description: 'Comida brasileira tradicional',
  phone: '+5511987654321',
  address: 'Av. dos Autonomistas, 1400 — Osasco, SP',
  distance_km: 1.2,
  categories: ['Brasileira'],
  average_rating: 4.8,
  review_count: 312,
  delivery_fee: 5.99,
  delivery_time_min: 25,
  delivery_time_max: 35,
  image_url: 'https://images.unsplash.com/photo-1544025162-d76694265947?w=600&h=400&fit=crop',
}

const apiDetail: ApiRestaurant = {
  ...apiRestaurant,
}

const apiReview: ApiReview = {
  id: 'rev-uuid-1',
  restaurant_id: 'api-uuid-1',
  user_id: 'u-uuid',
  user_name: 'Ana Souza',
  rating: 5,
  comment: 'Excelente comida!',
  created_at: '2026-10-28T19:30:00Z',
}

describe('catalog mappers', () => {
  it('mapeia review da API para o tipo da UI', () => {
    const review = mapApiReview(apiReview)

    expect(review.id).toBe('rev-uuid-1')
    expect(review.userName).toBe('Ana Souza')
    expect(review.rating).toBe(5)
    expect(review.comment).toBe('Excelente comida!')
    expect(review.userId).toBe('u-uuid')
    expect(review.date).toBe('28/10/2026')
  })

  it('mapeia review sem user_name usando fallback', () => {
    const review = mapApiReview({ ...apiReview, user_name: null })

    expect(review.userName).toBe('Cliente FoodFlow')
  })

  it('mapeia restaurante da API enriquecendo com mock', () => {
    const restaurant = mapApiRestaurant(apiRestaurant)

    expect(restaurant.id).toBe('api-uuid-1')
    expect(restaurant.name).toBe('Sabor da Vila')
    expect(restaurant.category).toBe('Brasileira')
    expect(restaurant.rating).toBe(4.8)
    expect(restaurant.reviewCount).toBe(312)
    expect(restaurant.distanceKm).toBe(1.2)
    expect(restaurant.deliveryFee).toBe(5.99)
    expect(restaurant.deliveryTimeMin).toBe(25)
    expect(restaurant.deliveryTimeMax).toBe(35)
    expect(restaurant.address).toBe('Av. dos Autonomistas, 1400 — Osasco, SP')
    expect(restaurant.phone).toBe('+5511987654321')
    expect(restaurant.isRecommended).toBe(false)
    expect(restaurant.menu.length).toBeGreaterThan(0)
    expect(restaurant.paymentMethods.length).toBeGreaterThan(0)
  })

  it('usa imagem de fallback quando a API não retorna', () => {
    const restaurant = mapApiRestaurant({
      ...apiRestaurant,
      image_url: null,
    })

    expect(restaurant.image).not.toBeNull()
    expect(restaurant.image).not.toBe('')
  })

  it('marca restaurante como recomendado quando solicitado', () => {
    const restaurant = mapApiRestaurant(apiRestaurant, true)

    expect(restaurant.isRecommended).toBe(true)
  })

  it('mapeia restaurante detalhado com avaliações', () => {
    const detail = mapApiRestaurantDetail({
      ...apiDetail,
      reviews: [apiReview],
    })

    expect(detail.reviews).toHaveLength(1)
    expect(detail.reviews[0].userName).toBe('Ana Souza')
    expect(detail.reviews[0].rating).toBe(5)
  })

  it('constrói mapa de IDs legados para UUIDs da API', () => {
    const apiRestaurants: ApiRestaurant[] = [
      { ...apiRestaurant, name: 'Sabor da Vila', id: 'uuid-sabor' },
      { ...apiRestaurant, name: 'Verde Vivo — Saudável', id: 'uuid-verde' },
    ]

    const mapping = buildLegacyIdMap(apiRestaurants)

    expect(mapping.get('r1')).toBe('uuid-sabor')
    expect(mapping.get('r2')).toBe('uuid-verde')
  })

  it('ignora restaurantes mock sem correspondência na API', () => {
    const apiRestaurants: ApiRestaurant[] = []

    const mapping = buildLegacyIdMap(apiRestaurants)

    expect(mapping.size).toBe(0)
  })
})
