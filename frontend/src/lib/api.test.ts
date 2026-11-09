import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import {
  searchRestaurants,
  getRestaurant,
  getRecommendations,
  createReview,
  updateReview,
  deleteReview,
  sendEvent,
  ApiError,
} from '@/lib/api'

function mockFetch(status: number, body: unknown, delay = 0) {
  return vi.fn(() =>
    new Promise<Response>((resolve) => {
      setTimeout(() => {
        const init: ResponseInit = { status, headers: { 'Content-Type': 'application/json' } }
        const bodyText = status === 204 ? null : JSON.stringify(body ?? null)
        resolve(new Response(bodyText, init))
      }, delay)
    })
  )
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  fetchMock.mockImplementation(mockFetch(200, []))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('busca restaurantes com parâmetros de coordenadas', async () => {
    await searchRestaurants({ lat: -23.5325, lon: -46.7939 })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/restaurants/search')
    expect(new URL(url).searchParams.get('lat')).toBe('-23.5325')
    expect(new URL(url).searchParams.get('lon')).toBe('-46.7939')
  })

  it('lança ApiError quando a resposta não é ok', async () => {
    fetchMock.mockImplementation(mockFetch(404, { detail: 'não encontrado' }))

    await expect(getRestaurant('r1')).rejects.toBeInstanceOf(ApiError)

    await expect(getRestaurant('r1')).rejects.toMatchObject({
      status: 404,
    })
  })

  it('lança ApiError quando a rede falha', async () => {
    fetchMock.mockRejectedValue(new TypeError('failed to fetch'))

    await expect(searchRestaurants({ lat: 0, lon: 0 })).rejects.toBeInstanceOf(
      ApiError
    )
  })

  it('envia avaliação com idempotency key', async () => {
    fetchMock.mockImplementation(mockFetch(201, { id: 'rev-1' }))

    await createReview(
      { restaurantId: 'r1', userId: 'u1', rating: 5, comment: 'Ótimo' },
      'idem-1'
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/reviews')
    expect(init?.method).toBe('POST')
    const rawHeaders = init?.headers
    const headersObj = rawHeaders && !Array.isArray(rawHeaders) && !(rawHeaders instanceof Headers)
      ? (rawHeaders as Record<string, string>)
      : {}
    const idempotencyKey = headersObj['Idempotency-Key']
    expect(idempotencyKey).toBe('idem-1')
    const body = JSON.parse(init?.body as string)
    expect(body.restaurant_id).toBe('r1')
    expect(body.rating).toBe(5)
  })

  it('atualiza avaliação existente', async () => {
    fetchMock.mockImplementation(mockFetch(200, { id: 'rev-1' }))

    await updateReview('rev-1', { userId: 'u1', rating: 4, comment: 'Bom' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/reviews/rev-1')
    expect(init?.method).toBe('PUT')
    const body = JSON.parse(init?.body as string)
    expect(body.rating).toBe(4)
  })

  it('remove avaliação com user_id como query', async () => {
    fetchMock.mockImplementation(mockFetch(204, null))

    await deleteReview('rev-1', 'u1')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url).toContain('/reviews/rev-1')
    expect(new URL(url).searchParams.get('user_id')).toBe('u1')
  })

  it('envia evento com tipo e payload', async () => {
    fetchMock.mockImplementation(mockFetch(201, { id: 'evt-1' }))

    await sendEvent('restaurant_opened', { restaurantId: 'r1' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/events')
    expect(init?.method).toBe('POST')
    const body = JSON.parse(init?.body as string)
    expect(body.type).toBe('restaurant_opened')
    expect(body.payload.restaurantId).toBe('r1')
  })
})
