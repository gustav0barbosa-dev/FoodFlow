/** Cliente HTTP tipado da API do FoodFlow. */

import { API_BASE_URL } from '@/lib/config'
import type {
  NearbyCategory,
  NearbyRestaurantsResponse,
} from '@/types'

const REQUEST_TIMEOUT_MS = 6000
// A Overpass API pode levar mais que o timeout padrão em regiões densas ou
// instâncias sobrecarregadas. O backend já aplica seu próprio timeout
// (OVERPASS_TIMEOUT_SECONDS + folga); aqui apenas evitamos abortar antes dele.
const NEARBY_REQUEST_TIMEOUT_MS = 50000

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
  source?: string | null
  osm_type?: string | null
  osm_id?: number | null
  latitude?: number | null
  longitude?: number | null
  cuisine?: string | null
  website?: string | null
  opening_hours?: string | null
  osm_url?: string | null
  dietary_tags?: string[]
  last_synced_at?: string | null
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

async function requestWithHeaders<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<{ data: T; headers: Headers }> {
  if (typeof fetch !== 'function') {
    throw new ApiError(0, 'API indisponível')
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)

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

    if (response.status === 204) {
      return { data: undefined as T, headers: response.headers }
    }
    return { data: (await response.json()) as T, headers: response.headers }
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (controller.signal.aborted) {
      throw new ApiError(504, 'A consulta demorou demais')
    }
    throw new ApiError(0, 'Não foi possível conectar à API')
  } finally {
    clearTimeout(timeout)
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<T> {
  return (await requestWithHeaders<T>(path, init, timeoutMs)).data
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

/**
 * Detalhe de um estabelecimento do OpenStreetMap.
 *
 * O backend persiste o restaurante na primeira abertura e devolve o UUID
 * interno, usado depois para registrar interações. A primeira consulta pode
 * atingir a Overpass API, por isso usa o timeout estendido.
 */
export function getOsmRestaurant(
  osmType: string,
  osmId: number,
  refresh = false
): Promise<ApiRestaurantDetail> {
  return request<ApiRestaurantDetail>(
    `/restaurants/osm/${encodeURIComponent(osmType)}/${osmId}${
      refresh ? '?refresh=true' : ''
    }`,
    {},
    NEARBY_REQUEST_TIMEOUT_MS
  )
}

export type ApiInteractionType =
  | 'IMPRESSION'
  | 'VIEW'
  | 'VIEW_DETAILS'
  | 'CLICK'
  | 'FAVORITE'
  | 'PURCHASE'
  | 'DISMISS'

export interface ApiInteraction {
  id: string
  user_id: string
  restaurant_id: string
  interaction_type: ApiInteractionType
  purchase_value: number | null
  experiment_group?: string | null
  experiment_mode?: string | null
  experiment_version?: string | null
  recommendation_id?: string | null
  recommendation_position?: number | null
  model_version?: string | null
  created_at: string
}

export function createInteraction(payload: {
  userId: string
  restaurantId: string
  interactionType: ApiInteractionType
  purchaseValue?: number
  idempotencyKey?: string
  experimentGroup?: string
  experimentMode?: 'experiment' | 'demo'
  experimentVersion?: string
  recommendationId?: string
  recommendationPosition?: number
  modelVersion?: string
  metadata?: Record<string, unknown>
}): Promise<ApiInteraction> {
  return request<ApiInteraction>('/interactions', {
    method: 'POST',
    body: JSON.stringify({
      user_id: payload.userId,
      restaurant_id: payload.restaurantId,
      interaction_type: payload.interactionType,
      purchase_value: payload.purchaseValue,
      idempotency_key: payload.idempotencyKey,
      experiment_group: payload.experimentGroup,
      experiment_mode: payload.experimentMode,
      experiment_version: payload.experimentVersion,
      recommendation_id: payload.recommendationId,
      recommendation_position: payload.recommendationPosition,
      model_version: payload.modelVersion,
      metadata: payload.metadata ?? {},
    }),
  })
}

export interface ApiPreferenceItem {
  name: string
  score: number
}

export interface ApiUserPreferences {
  user_id: string
  total_interactions: number
  views: number
  clicks: number
  favorites: number
  purchases: number
  impressions?: number
  dismissals?: number
  total_spent: number
  average_purchase_value: number
  top_categories: ApiPreferenceItem[]
  top_cuisines: ApiPreferenceItem[]
  top_restaurants: Array<{
    restaurant_id: string
    name: string
    score: number
    purchases: number
  }>
}

export function getUserPreferences(
  userId: string
): Promise<ApiUserPreferences> {
  return request<ApiUserPreferences>(`/users/${userId}/preferences`)
}

/**
 * Busca restaurantes reais próximos via OpenStreetMap (Overpass API).
 *
 * Endpoint separado do catálogo próprio: os resultados não têm cardápio nem
 * dados de entrega e devem ser exibidos com atribuição do OpenStreetMap.
 */
export function searchNearbyRestaurants({
  lat,
  lon,
  radius = 3000,
  category,
}: {
  lat: number
  lon: number
  radius?: number
  category?: NearbyCategory
}): Promise<NearbyRestaurantsResponse> {
  return request<NearbyRestaurantsResponse>(
    `/restaurants/nearby?${query({ lat, lon, radius, category })}`,
    {},
    NEARBY_REQUEST_TIMEOUT_MS
  )
}

export interface RecommendationResult {
  recommendations: ApiRecommendation[]
  experimentGroup: string
  experimentMode: 'experiment' | 'demo'
  experimentVersion: string
  recommendationId: string
  modelVersion: string
  strategy: string
}

export async function getRecommendations({
  userId,
  lat,
  lon,
  turno,
  experiment,
  mode = 'experiment',
}: {
  userId: string
  lat: number
  lon: number
  turno: string
  experiment?: string
  mode?: 'experiment' | 'demo'
}): Promise<RecommendationResult> {
  // No modo experimental a estratégia manual é ignorada pelo backend; não a
  // enviamos para deixar explícito que a atribuição é persistente.
  const requestedStrategy = mode === 'demo' ? experiment : undefined
  const { data, headers } = await requestWithHeaders<ApiRecommendation[]>(
    `/recommendations?${query({
      user_id: userId,
      lat,
      lon,
      turno,
      mode,
      experiment: requestedStrategy,
    })}`
  )

  return {
    recommendations: data,
    experimentGroup:
      headers.get('X-Experiment-Group') ?? requestedStrategy ?? '',
    experimentMode:
      (headers.get('X-Experiment-Mode') as 'experiment' | 'demo' | null) ??
      mode,
    experimentVersion: headers.get('X-Experiment-Version') ?? '',
    recommendationId: headers.get('X-Recommendation-Id') ?? '',
    modelVersion: headers.get('X-Model-Version') ?? '',
    strategy: headers.get('X-Recommendation-Strategy') ?? '',
  }
}

export interface ApiConfidenceInterval {
  low: number
  high: number
}

export interface ApiExperimentGroupMetrics {
  label: string
  users: number
  impressions: number
  clicks: number
  views: number
  view_details: number
  favorites: number
  purchases: number
  dismissals: number
  distinct_restaurants: number
  ctr: number
  conversion_rate: number
  detail_rate: number
  favorite_rate: number
  dismiss_rate: number
  detail_per_click: number
  impressions_per_user: number
  clicks_per_user: number
  purchases_per_user: number
  catalog_diversity: number
  model_versions: string[]
  confidence_intervals: {
    ctr: ApiConfidenceInterval | null
    detail_rate: ApiConfidenceInterval | null
    conversion_rate: ApiConfidenceInterval | null
  }
  readable: boolean
  conversion_readable: boolean
  /** Presentes apenas na coorte válida. */
  users_with_impressions?: number
  user_ctr?: number
  user_conversion_rate?: number
  conversion_per_user?: number
  user_confidence_intervals?: {
    ctr: ApiBootstrapInterval | null
    conversion_rate: ApiBootstrapInterval | null
    conversion_per_user: ApiBootstrapInterval | null
  }
}

export interface ApiBootstrapInterval {
  low: number
  high: number
  resamples: number
  unit: string
}

export interface ApiExperimentComparison {
  metric: string
  group: string
  baseline: string
  absolute_difference: number
  relative_lift: number | null
  p_value: number | null
  significant: boolean
  method?: string
  confidence_interval?: ApiBootstrapInterval | null
  user_level?: {
    candidate_mean: number | null
    baseline_mean: number | null
    absolute_difference: number | null
  }
}

export interface ApiStatisticalAnalysis {
  available: boolean
  reason?: string
  method?: string
  alpha?: number
  corrected_alpha?: number
  planned_comparisons?: number
  unit?: string
  bootstrap_resamples?: number
  comparisons?: ApiExperimentComparison[]
  notes?: string[]
}

export interface ApiExperimentSampleSizeEntry {
  metric: string
  baseline_rate: number
  expected_rate: number | null
  required_users_per_group: number | null
  required_impressions_per_group: number | null
  reason: string | null
}

export interface ApiExperimentPlan {
  primary_metric: string
  unit: string
  alpha: number
  corrected_alpha: number
  power: number
  planned_comparisons: number
  minimum_detectable_effect_relative: number
  baseline_impressions_per_user: number
  plans: ApiExperimentSampleSizeEntry[]
  note: string
}

export interface ApiExperimentTimelinePoint {
  date: string
  groups: Record<
    string,
    {
      impressions: number
      clicks: number
      purchases: number
      ctr: number
      conversion_rate: number
    }
  >
}

export type ApiExperimentPhase =
  | 'collecting'
  | 'insufficient_data'
  | 'ready'
  | 'statistical_analysis'

export interface ApiExperimentResults {
  source: string
  phase: ApiExperimentPhase
  message: string
  generated_at: string
  has_data: boolean
  has_valid_data?: boolean
  experiment_version: string
  unit: string
  minimum_impressions_for_reading: number
  thresholds: {
    min_impressions: number
    min_users_per_group: number
    min_clicks_per_group: number
    min_purchases_per_group: number
    statistical_min_impressions: number
    statistical_min_users_per_group: number
  }
  total_impressions: number
  total_clicks: number
  total_purchases: number
  valid_total_impressions?: number
  valid_total_clicks?: number
  valid_total_purchases?: number
  exposed_users: number
  valid_exposed_users?: number
  unique_users: number
  assignment_counts: Record<string, number>
  untagged_events: number
  demo_events: number
  contaminated_users: number
  contamination_rate?: number
  contamination_detected: boolean
  valid_cohort?: {
    excluded_users: number
    contamination_rate: number
    users: number
    raw_users: number
    impressions: number
    raw_impressions: number
    note: string
  }
  groups: Record<string, ApiExperimentGroupMetrics>
  valid_groups?: Record<string, ApiExperimentGroupMetrics>
  comparison: {
    best_ctr: string | null
    best_conversion: string | null
    winner_declared: boolean
    note: string
  }
  statistical_analysis: ApiStatisticalAnalysis
  plan?: ApiExperimentPlan
  periods: Record<
    string,
    { first_event_at: string | null; last_event_at: string | null }
  >
  timeline: ApiExperimentTimelinePoint[]
  coverage_definition: string
  request_counters?: {
    redis_available: boolean
    total_requests: number
    baseline_requests: number
    personalized_requests: number
    distance_requests: number
    baseline_share: number
    personalized_share: number
    distance_share: number
  }
}

export function getABTestResults(): Promise<ApiExperimentResults> {
  return request<ApiExperimentResults>('/experiment/ab-test')
}

export interface ApiRankingMetrics {
  k: number
  contexts: number
  contexts_total: number
  contexts_without_candidates: number
  contexts_without_relevance: number
  total_relevant: number
  precision_at_k: number
  recall_at_k: number
  ndcg_at_k: number
  map_at_k: number
  ild_at_k?: number | null
  novelty_at_k?: number | null
  /** Alias histórico de ``catalog_coverage``. */
  coverage: number
  catalog_coverage: number
  user_coverage: number
  distinct_recommended: number
  catalog_size: number
  users_with_recommendations: number
  users: number
  confidence_intervals?: Record<string, ApiBootstrapInterval | null>
}

export interface ApiSplitStats {
  samples: number
  contexts: number
  users: number
  positives: number
  negatives: number
  observed_negatives?: number
  unobserved_negatives?: number
  period: { start: string | null; end: string | null }
}

export interface ApiTrainingMetrics {
  available: boolean
  message?: string
  model_loaded: boolean
  loaded_model_version?: string | null
  schema_version?: number
  model_version?: string
  trained_at?: string
  source?: string
  model?: string
  target?: string
  label_semantics?: string
  negative_policy?: string
  dataset?: {
    hash: string
    samples: number
    users: number
    contexts: number
    restaurants: number
    positives: number
    negatives: number
    observed_negatives?: number
    unobserved_negatives?: number
    relevance_distribution: Record<string, number>
    period: { start: string | null; end: string | null }
    feature_count: number
  }
  features?: string[]
  params?: Record<string, unknown>
  seed?: number
  split?: {
    strategy: string
    boundaries: {
      train_end: string | null
      validation_end: string | null
      test_end: string | null
    }
    train: ApiSplitStats
    validation: ApiSplitStats
    test: ApiSplitStats
    train_samples: number
    validation_samples: number
    test_samples: number
    contexts: Record<string, number>
  }
  metrics?: {
    roc_auc: number | null
    roc_auc_available: boolean
    roc_auc_note: string | null
    pr_auc?: number | null
    brier_score?: number | null
    log_loss?: number | null
    validation_roc_auc: number | null
    test_roc_auc: number | null
    evaluation_split: string
    ranking: ApiRankingMetrics
  }
  baselines?: Record<string, ApiRankingMetrics>
  production?: {
    available: boolean
    reason: string | null
    model_version: string | null
    evaluation_split: string | null
    ranking: ApiRankingMetrics | null
  }
  comparison?: Record<string, number | null>
  quality?: {
    ok: boolean
    promotion_ready: boolean
    checks: Record<string, boolean>
    promotion_checks: Record<string, boolean>
    limitations: string[]
  }
  promotion?: {
    decision:
      | 'bootstrap'
      | 'promoted'
      | 'kept_previous'
      | 'rejected_quality'
      | 'insufficient_evidence'
    promoted: boolean
    reason: string
    candidate_path?: string
    previous_model_version?: string | null
    archived_previous_path?: string
  }
  phase?: 'experimental' | 'ready'
}

export function getTrainingMetrics(): Promise<ApiTrainingMetrics> {
  return request<ApiTrainingMetrics>('/ml/metrics')
}

export interface StreetViewMetadata {
  available: boolean
  status: string
  pano_id?: string
  latitude?: number
  longitude?: number
  copyright?: string
}

export function getStreetViewMetadata({
  lat,
  lon,
  radius = 50,
}: {
  lat: number
  lon: number
  radius?: number
}): Promise<StreetViewMetadata> {
  return request<StreetViewMetadata>(
    `/street-view/metadata?${query({ lat, lon, radius })}`
  )
}

/** URL do proxy de imagem; a chave da Google API nunca chega ao navegador. */
export function streetViewImageUrl({
  lat,
  lon,
  width = 600,
  height = 400,
}: {
  lat: number
  lon: number
  width?: number
  height?: number
}): string {
  return `${API_BASE_URL}/street-view/image?${query({ lat, lon, width, height })}`
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
