/** Cliente HTTP tipado da API do FoodFlow. */

import { API_BASE_URL } from '@/lib/config'

const REQUEST_TIMEOUT_MS = 6000

export interface ApiRestaurant {
  id: string
  name: string
  description: string | null
  phone: string | null
  address: string
  distance_km: number | null
  categories: string[]
  average_rating: number
  review_count: number
  delivery_fee: number
  delivery_time_min: number
  delivery_time_max: number
  image_url: string | null
}

export interface ApiReview {
  id: string
  restaurant_id: string
  user_id: string
  user_name: string | null
  rating: number
  comment: string | null
  created_at: string
}

export interface ApiRestaurantDetail extends ApiRestaurant {
  reviews: ApiReview[]
}

export interface ApiRecommendation extends ApiRestaurant {
  score: number
}

export type ApiEventType =
  | 'restaurant_card_clicked'
  | 'restaurant_opened'
  | 'add_to_cart'
  | 'order_completed'
  | 'preferences_updated'
  | 'search_performed'
  | 'favorite_toggled'
  | 'order_status_updated'
  | 'review_submitted'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    Object.setPrototypeOf(this, ApiError.prototype)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (typeof fetch !== 'function') {
    throw new ApiError(0, 'API indisponível')
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    if (init.body) headers.set('Content-Type', 'application/json')

    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers,
    })

    if (!response.ok) {
      let detail = `Erro ${response.status} na API`
      try {
        const body = (await response.json()) as { detail?: string }
        if (body.detail) detail = body.detail
      } catch {
        // Mantém a mensagem genérica quando a resposta não é JSON.
      }
      throw new ApiError(response.status, detail)
    }

    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(0, 'Não foi possível conectar à API')
  } finally {
    clearTimeout(timeout)
  }
}

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }

  return search.toString()
}

export function searchRestaurants({
  lat,
  lon,
  radiusKm = 50,
  limit = 100,
  offset = 0,
}: {
  lat: number
  lon: number
  radiusKm?: number
  limit?: number
  offset?: number
}): Promise<ApiRestaurant[]> {
  return request<ApiRestaurant[]>(
    `/restaurants/search?${query({
      lat,
      lon,
      radius_km: radiusKm,
      limit,
      offset,
    })}`
  )
}

export function getRestaurant(id: string): Promise<ApiRestaurantDetail> {
  return request<ApiRestaurantDetail>(`/restaurants/${id}`)
}

export function getRecommendations({
  userId,
  lat,
  lon,
  turno,
  experiment,
}: {
  userId: string
  lat: number
  lon: number
  turno: string
  experiment?: string
}): Promise<ApiRecommendation[]> {
  return request<ApiRecommendation[]>(
    `/recommendations?${query({ user_id: userId, lat, lon, turno, experiment })}`
  )
}

export function getABTestResults(): Promise<{
  redis_available: boolean
  total_requests: number
  personalized_requests: number
  distance_requests: number
  personalized_share: number
  distance_share: number
}> {
  return request('/experiment/ab-test')
}

export function createReview(
  payload: {
    restaurantId: string
    userId: string
    rating: number
    comment: string
  },
  idempotencyKey?: string
): Promise<ApiReview> {
  return request<ApiReview>('/reviews', {
    method: 'POST',
    body: JSON.stringify({
      restaurant_id: payload.restaurantId,
      user_id: payload.userId,
      rating: payload.rating,
      comment: payload.comment,
    }),
    headers: idempotencyKey
      ? { 'Idempotency-Key': idempotencyKey }
      : undefined,
  })
}

export function updateReview(
  reviewId: string,
  payload: { userId: string; rating: number; comment: string }
): Promise<ApiReview> {
  return request<ApiReview>(`/reviews/${reviewId}`, {
    method: 'PUT',
    body: JSON.stringify({
      user_id: payload.userId,
      rating: payload.rating,
      comment: payload.comment,
    }),
  })
}

export function deleteReview(reviewId: string, userId: string) {
  return request<void>(
    `/reviews/${reviewId}?${query({ user_id: userId })}`,
    { method: 'DELETE' }
  )
}

export function sendEvent(
  type: ApiEventType,
  payload: Record<string, unknown>
) {
  return request<{ id: string }>('/events', {
    method: 'POST',
    body: JSON.stringify({ type, payload }),
  })
}
