import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import {
  searchRestaurants,
  searchNearbyRestaurants,
  getRestaurant,
  getOsmRestaurant,
  createInteraction,
  getUserPreferences,
  createReview,
  updateReview,
  deleteReview,
  sendEvent,
  getRecommendations,
  getABTestResults,
  getTrainingMetrics,
  getStreetViewMetadata,
  streetViewImageUrl,
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

  it('converte abort por timeout em ApiError 504', async () => {
    vi.useFakeTimers()

    try {
      fetchMock.mockImplementation(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () =>
              reject(new DOMException('Aborted', 'AbortError'))
            )
          })
      )

      const pending = searchRestaurants({ lat: 0, lon: 0 })
      const assertion = expect(pending).rejects.toMatchObject({ status: 504 })
      await vi.advanceTimersByTimeAsync(6000)
      await assertion
    } finally {
      vi.useRealTimers()
    }
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
    let idempotencyKey: string | undefined
    if (rawHeaders && typeof (rawHeaders as Headers).get === 'function') {
      idempotencyKey = (rawHeaders as Headers).get('Idempotency-Key') ?? undefined
    } else if (rawHeaders && !Array.isArray(rawHeaders)) {
      idempotencyKey = (rawHeaders as Record<string, string>)['Idempotency-Key']
    }
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

  it('busca restaurantes do OpenStreetMap com raio e categoria', async () => {
    await searchNearbyRestaurants({
      lat: -23.5227,
      lon: -46.1878,
      radius: 3000,
      category: 'cafe',
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/restaurants/nearby')
    expect(new URL(url).searchParams.get('lat')).toBe('-23.5227')
    expect(new URL(url).searchParams.get('lon')).toBe('-46.1878')
    expect(new URL(url).searchParams.get('radius')).toBe('3000')
    expect(new URL(url).searchParams.get('category')).toBe('cafe')
  })

  it('usa raio padrão de 3 km na busca OSM', async () => {
    await searchNearbyRestaurants({ lat: 0, lon: 0 })

    const url = fetchMock.mock.calls[0][0] as string
    expect(new URL(url).searchParams.get('radius')).toBe('3000')
    expect(new URL(url).searchParams.get('category')).toBeNull()
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

  it('busca detalhe do OSM pelo par tipo/id', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, { id: 'osm-uuid', reviews: [] })
    )

    await getOsmRestaurant('node', 123456789)

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/restaurants/osm/node/123456789')
    expect(new URL(url).searchParams.get('refresh')).toBeNull()
  })

  it('permite forçar atualização do detalhe do OSM', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, { id: 'osm-uuid', reviews: [] })
    )

    await getOsmRestaurant('way', 42, true)

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/restaurants/osm/way/42')
    expect(new URL(url).searchParams.get('refresh')).toBe('true')
  })

  it('registra interação com valor de compra e chave de idempotência', async () => {
    fetchMock.mockImplementation(
      mockFetch(201, { id: 'interaction-1' })
    )

    await createInteraction({
      userId: 'u1',
      restaurantId: 'r1',
      interactionType: 'PURCHASE',
      purchaseValue: 59.9,
      idempotencyKey: 'order-1:r1',
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/interactions')
    expect(init?.method).toBe('POST')
    const body = JSON.parse(init?.body as string)
    expect(body.user_id).toBe('u1')
    expect(body.restaurant_id).toBe('r1')
    expect(body.interaction_type).toBe('PURCHASE')
    expect(body.purchase_value).toBe(59.9)
    expect(body.idempotency_key).toBe('order-1:r1')
  })

  it('busca o perfil de preferências do usuário', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, { user_id: 'u1', purchases: 2 })
    )

    const profile = await getUserPreferences('u1')

    expect(fetchMock.mock.calls[0][0]).toContain('/users/u1/preferences')
    expect(profile.purchases).toBe(2)
  })

  it('envia contexto experimental na interação', async () => {
    fetchMock.mockImplementation(mockFetch(201, { id: 'interaction-1' }))

    await createInteraction({
      userId: 'u1',
      restaurantId: 'r1',
      interactionType: 'CLICK',
      experimentGroup: 'personalized',
      experimentMode: 'experiment',
      experimentVersion: '2026-11-v1',
      recommendationId: 'rec-123',
      recommendationPosition: 3,
      modelVersion: 'lgbm-2026',
      metadata: { source: 'home_featured' },
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const body = JSON.parse(init?.body as string)
    expect(body.experiment_group).toBe('personalized')
    expect(body.experiment_mode).toBe('experiment')
    expect(body.experiment_version).toBe('2026-11-v1')
    expect(body.recommendation_id).toBe('rec-123')
    expect(body.recommendation_position).toBe(3)
    expect(body.model_version).toBe('lgbm-2026')
    expect(body.metadata).toEqual({ source: 'home_featured' })
  })

  it('lê o contexto A/B dos headers das recomendações', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
            'X-Experiment-Group': 'distance',
            'X-Experiment-Mode': 'demo',
            'X-Experiment-Version': '2026-11-v1',
            'X-Recommendation-Id': 'rec-1',
            'X-Model-Version': 'lgbm-abc',
            'X-Recommendation-Strategy': 'distance',
          },
        })
      )
    )

    const result = await getRecommendations({
      userId: 'u1',
      lat: -23.5,
      lon: -46.7,
      turno: 'noite',
      mode: 'demo',
      experiment: 'distance',
    })

    expect(result.experimentGroup).toBe('distance')
    expect(result.experimentMode).toBe('demo')
    expect(result.experimentVersion).toBe('2026-11-v1')
    expect(result.recommendationId).toBe('rec-1')
    expect(result.modelVersion).toBe('lgbm-abc')
    expect(result.strategy).toBe('distance')
    expect(result.recommendations).toEqual([])
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/recommendations')
    expect(new URL(url).searchParams.get('mode')).toBe('demo')
    expect(new URL(url).searchParams.get('experiment')).toBe('distance')
  })

  it('não envia estratégia manual no modo experimental', async () => {
    fetchMock.mockImplementation(mockFetch(200, []))

    await getRecommendations({
      userId: 'u1',
      lat: 0,
      lon: 0,
      turno: 'tarde',
      mode: 'experiment',
      experiment: 'distance',
    })

    const url = fetchMock.mock.calls[0][0] as string
    expect(new URL(url).searchParams.get('mode')).toBe('experiment')
    expect(new URL(url).searchParams.get('experiment')).toBeNull()
  })

  it('usa fallback do grupo quando o header não vem', async () => {
    fetchMock.mockImplementation(mockFetch(200, []))

    const result = await getRecommendations({
      userId: 'u1',
      lat: 0,
      lon: 0,
      turno: 'tarde',
      mode: 'demo',
      experiment: 'baseline',
    })

    expect(result.experimentGroup).toBe('baseline')
    expect(result.experimentMode).toBe('demo')
    expect(result.experimentVersion).toBe('')
    expect(result.recommendationId).toBe('')
    expect(result.modelVersion).toBe('')
  })

  it('busca métricas do experimento A/B no banco', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, {
        source: 'database',
        phase: 'collecting',
        groups: { baseline: { impressions: 0 } },
      })
    )

    const results = await getABTestResults()

    expect(fetchMock.mock.calls[0][0]).toContain('/experiment/ab-test')
    expect(results.source).toBe('database')
    expect(results.groups.baseline.impressions).toBe(0)
  })

  it('busca métricas do último treino', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, { available: true, model_version: 'lgbm-1' })
    )

    const report = await getTrainingMetrics()

    expect(fetchMock.mock.calls[0][0]).toContain('/ml/metrics')
    expect(report.model_version).toBe('lgbm-1')
  })

  it('consulta metadata do Street View com raio', async () => {
    fetchMock.mockImplementation(
      mockFetch(200, { available: false, status: 'ZERO_RESULTS' })
    )

    const metadata = await getStreetViewMetadata({
      lat: -23.5,
      lon: -46.7,
      radius: 80,
    })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/street-view/metadata')
    expect(new URL(url).searchParams.get('radius')).toBe('80')
    expect(metadata.status).toBe('ZERO_RESULTS')
  })

  it('monta a URL do proxy de imagem sem expor chave', () => {
    const url = streetViewImageUrl({
      lat: -23.5,
      lon: -46.7,
      width: 320,
      height: 200,
    })

    expect(url).toContain('/street-view/image')
    const parsed = new URL(url)
    expect(parsed.searchParams.get('lat')).toBe('-23.5')
    expect(parsed.searchParams.get('width')).toBe('320')
    expect(parsed.searchParams.get('key')).toBeNull()
  })
})
