/** Conversão entre os contratos da API e os tipos usados pela UI. */

import { restaurants as mockRestaurants } from '@/data/mockData'
import type {
  ApiRestaurant,
  ApiRestaurantDetail,
  ApiReview,
} from '@/lib/api'
import { categoryLabel } from '@/lib/osm'
import type { Restaurant, RestaurantSource, Review } from '@/types'

const FALLBACK_IMAGE =
  'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=600&h=400&fit=crop'

const mockByName = new Map(
  mockRestaurants.map((restaurant) => [restaurant.name, restaurant])
)

function osmTypeOf(
  value: string | null | undefined
): Restaurant['osmType'] {
  return value === 'node' || value === 'way' || value === 'relation'
    ? value
    : undefined
}

function sourceOf(value: string | null | undefined): RestaurantSource {
  return value === 'osm' ? 'osm' : 'foodflow'
}

export function formatReviewDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

export function mapApiReview(review: ApiReview): Review {
  return {
    id: review.id,
    userName: review.user_name ?? 'Cliente FoodFlow',
    rating: review.rating,
    date: formatReviewDate(review.created_at),
    comment: review.comment ?? '',
    userId: review.user_id,
  }
}

export function mapApiRestaurant(
  restaurant: ApiRestaurant,
  isRecommended = false
): Restaurant {
  const source = sourceOf(restaurant.source)

  // Restaurantes do OSM não são enriquecidos com dados do catálogo mock:
  // cardápio, avaliações, taxa e tempo de entrega simplesmente não existem.
  if (source === 'osm') {
    return {
      id: restaurant.id,
      name: restaurant.name,
      category: categoryLabel(restaurant.categories[0] ?? null),
      image: '',
      rating: restaurant.average_rating,
      reviewCount: restaurant.review_count,
      distanceKm: restaurant.distance_km ?? 0,
      deliveryFee: restaurant.delivery_fee,
      deliveryTimeMin: restaurant.delivery_time_min,
      deliveryTimeMax: restaurant.delivery_time_max,
      address: restaurant.address ?? '',
      phone: restaurant.phone ?? '',
      tags: [],
      dietaryTags: [],
      isRecommended,
      menu: [],
      reviews: [],
      hours: restaurant.opening_hours ?? '',
      paymentMethods: [],
      source,
      osmType: osmTypeOf(restaurant.osm_type),
      osmId: restaurant.osm_id ?? undefined,
      latitude: restaurant.latitude ?? undefined,
      longitude: restaurant.longitude ?? undefined,
      cuisine: restaurant.cuisine ?? undefined,
      website: restaurant.website ?? undefined,
      openingHours: restaurant.opening_hours ?? undefined,
      osmUrl: restaurant.osm_url ?? undefined,
    }
  }

  const mock = mockByName.get(restaurant.name)

  return {
    id: restaurant.id,
    name: restaurant.name,
    category: restaurant.categories[0] ?? mock?.category ?? 'Restaurante',
    image: restaurant.image_url ?? mock?.image ?? FALLBACK_IMAGE,
    rating: restaurant.average_rating,
    reviewCount: restaurant.review_count,
    distanceKm: restaurant.distance_km ?? mock?.distanceKm ?? 0,
    deliveryFee: restaurant.delivery_fee,
    deliveryTimeMin: restaurant.delivery_time_min,
    deliveryTimeMax: restaurant.delivery_time_max,
    address: restaurant.address,
    phone: restaurant.phone ?? mock?.phone ?? '',
    tags: mock?.tags ?? [],
    dietaryTags: mock?.dietaryTags ?? [],
    isRecommended,
    menu: mock?.menu ?? [],
    reviews: [],
    hours: mock?.hours ?? 'Consulte o restaurante',
    paymentMethods: mock?.paymentMethods ?? ['Cartão', 'Pix', 'Dinheiro'],
    source,
  }
}

export function mapApiRestaurantDetail(
  detail: ApiRestaurantDetail,
  isRecommended = false
): Restaurant {
  return {
    ...mapApiRestaurant(detail, isRecommended),
    reviews: detail.reviews.map(mapApiReview),
  }
}

/** Mapeia os IDs do catálogo mock para os UUIDs devolvidos pela API. */
export function buildLegacyIdMap(
  apiRestaurants: ApiRestaurant[]
): Map<string, string> {
  const apiByName = new Map(
    apiRestaurants.map((restaurant) => [restaurant.name, restaurant.id])
  )
  const mapping = new Map<string, string>()

  for (const mock of mockRestaurants) {
    const apiId = apiByName.get(mock.name)
    if (apiId) mapping.set(mock.id, apiId)
  }

  return mapping
}

/**
 * Equivalente ao `buildLegacyIdMap`, mas a partir do catálogo já mapeado para
 * a UI. Serve para resolver links antigos (`/restaurante/r1`) mesmo quando a
 * página de detalhe é aberta diretamente, sem passar pela Home.
 */
export function buildCatalogIdMap(
  restaurants: Restaurant[]
): Map<string, string> {
  const currentIdByName = new Map(
    restaurants.map((restaurant) => [restaurant.name, restaurant.id])
  )
  const mapping = new Map<string, string>()

  for (const mock of mockRestaurants) {
    const currentId = currentIdByName.get(mock.name)
    if (currentId) mapping.set(mock.id, currentId)
  }

  return mapping
}
