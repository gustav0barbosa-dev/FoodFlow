import { describe, expect, it } from 'vitest'
import {
  mapApiMenuItem,
  mapApiReview,
  mapApiRestaurant,
  mapApiRestaurantDetail,
  withApiMenu,
  buildCatalogIdMap,
  buildLegacyIdMap,
} from '@/lib/catalog'
import type { ApiMenuItem, ApiRestaurant, ApiReview } from '@/lib/api'

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

const apiMenuItem: ApiMenuItem = {
  id: 'menu-uuid-1',
  section: 'Pizzas',
  name: 'Pizza Margherita',
  description: 'Molho, mussarela e manjericão.',
  price: 49.9,
  image_url: null,
  dietary_tags: ['Vegetariano'],
  is_available: true,
  source: 'synthetic',
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

  it('mapeia item de cardápio e preserva a origem sintética', () => {
    const item = mapApiMenuItem(apiMenuItem)

    expect(item.id).toBe('menu-uuid-1')
    expect(item.section).toBe('Pizzas')
    expect(item.price).toBe(49.9)
    expect(item.dietaryTags).toEqual(['Vegetariano'])
    expect(item.source).toBe('synthetic')
    expect(item.image).not.toBe('')
  })

  it('substitui o cardápio pelo endpoint quando há itens', () => {
    const restaurant = withApiMenu(
      mapApiRestaurant({ ...apiRestaurant, source: 'synthetic' }),
      [apiMenuItem]
    )

    expect(restaurant.menu).toHaveLength(1)
    expect(restaurant.menu[0].name).toBe('Pizza Margherita')
    expect(restaurant.menu[0].source).toBe('synthetic')
  })

  it('não enriquece restaurante sintético com o catálogo mock', () => {
    const restaurant = mapApiRestaurant({
      ...apiRestaurant,
      source: 'synthetic',
    })

    expect(restaurant.source).toBe('synthetic')
    expect(restaurant.menu).toEqual([])
  })

  it('passa o cardápio do endpoint no detalhe', () => {
    const detail = mapApiRestaurantDetail(
      { ...apiDetail, reviews: [] },
      false,
      [apiMenuItem]
    )

    expect(detail.menu).toHaveLength(1)
    expect(detail.menu[0].source).toBe('synthetic')
  })

  it('não enriquece restaurantes do OSM com dados do catálogo mock', () => {
    const restaurant = mapApiRestaurant({
      ...apiRestaurant,
      id: 'osm-uuid',
      name: 'Sabor da Vila',
      source: 'osm',
      osm_type: 'node',
      osm_id: 123,
      latitude: -23.5,
      longitude: -46.6,
      cuisine: 'italian',
      website: null,
      opening_hours: null,
      osm_url: 'https://www.openstreetmap.org/node/123',
      categories: ['restaurant'],
      address: '',
      phone: null,
      average_rating: 0,
      review_count: 0,
      delivery_fee: 0,
      image_url: null,
    })

    expect(restaurant.source).toBe('osm')
    expect(restaurant.category).toBe('Restaurante')
    expect(restaurant.cuisine).toBe('italian')
    expect(restaurant.osmType).toBe('node')
    expect(restaurant.osmId).toBe(123)
    expect(restaurant.image).toBe('')
    expect(restaurant.menu).toEqual([])
    expect(restaurant.reviews).toEqual([])
    expect(restaurant.paymentMethods).toEqual([])
    expect(restaurant.tags).toEqual([])
    expect(restaurant.address).toBe('')
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

  it('constrói mapa de IDs legados a partir do catálogo da UI', () => {
    const catalog = [
      mapApiRestaurant({ ...apiRestaurant, name: 'Sabor da Vila', id: 'uuid-sabor' }),
      mapApiRestaurant({
        ...apiRestaurant,
        name: 'Verde Vivo — Saudável',
        id: 'uuid-verde',
      }),
    ]

    const mapping = buildCatalogIdMap(catalog)

    expect(mapping.get('r1')).toBe('uuid-sabor')
    expect(mapping.get('r2')).toBe('uuid-verde')
    expect(mapping.get('r3')).toBeUndefined()
  })
})
