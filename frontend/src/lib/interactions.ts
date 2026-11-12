/** Registro best-effort do comportamento do usuário para o recomendador. */

import { createInteraction, type ApiInteractionType } from '@/lib/api'
import { API_USER_ID, isUuid, type ExperimentMode } from '@/lib/config'

export interface InteractionOptions {
  purchaseValue?: number
  idempotencyKey?: string
  /**
   * Contexto da exposição que originou o evento: grupo, modo, versão do
   * experimento, identificador da recomendação, posição no ranking e versão
   * do modelo. Sem esses campos o evento não pode ser atribuído corretamente.
   */
  experimentGroup?: string
  experimentMode?: ExperimentMode
  experimentVersion?: string
  recommendationId?: string
  recommendationPosition?: number
  modelVersion?: string
  metadata?: Record<string, unknown>
}

/**
 * Envia uma interação sem bloquear a UI.
 *
 * Falhas de rede/API são ignoradas de propósito: rastrear comportamento não
 * pode impedir a navegação nem a finalização de um pedido. IDs locais (mock)
 * não são enviados porque o backend só conhece restaurantes persistidos.
 */
export function trackInteraction(
  restaurantId: string | null | undefined,
  interactionType: ApiInteractionType,
  options: InteractionOptions = {}
): void {
  if (!isUuid(restaurantId) || !isUuid(API_USER_ID)) return

  void createInteraction({
    userId: API_USER_ID,
    restaurantId,
    interactionType,
    purchaseValue: options.purchaseValue,
    idempotencyKey: options.idempotencyKey,
    experimentGroup: options.experimentGroup,
    experimentMode: options.experimentMode,
    experimentVersion: options.experimentVersion,
    recommendationId: options.recommendationId,
    recommendationPosition: options.recommendationPosition,
    modelVersion: options.modelVersion,
    metadata: options.metadata,
  }).catch(() => {
    // Melhor esforço: o histórico é complementar e não deve quebrar a UI.
  })
}
