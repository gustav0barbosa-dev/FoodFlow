/** Configuração de integração do frontend com a API do FoodFlow. */

export type Turno = 'manha' | 'tarde' | 'noite' | 'madrugada'

export type ABGroup = 'personalized' | 'distance' | ''

function readNumber(value: string | undefined, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

/**
 * No Windows, `localhost` costuma resolver para IPv6 (`::1`), enquanto o
 * Docker publica a API apenas em IPv4. Normalizamos loopback para 127.0.0.1
 * para que o navegador não fique preso até o timeout da requisição.
 */
function normalizeApiUrl(value: string) {
  return value
    .replace(/\/\/(localhost|\[::1\])(?=[:/]|$)/i, '//127.0.0.1')
    .replace(/\/+$/, '')
}

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1'

export const API_BASE_URL = normalizeApiUrl(apiUrl)

/** Usuário demo do seed: Ana Souza. */
export const DEFAULT_USER_ID =
  import.meta.env.VITE_USER_ID ?? 'a54a52c3-8543-56d3-8e4b-6d8220667bd5'

export const DEFAULT_LATITUDE = readNumber(
  import.meta.env.VITE_DEFAULT_LAT,
  -23.5325
)

export const DEFAULT_LONGITUDE = readNumber(
  import.meta.env.VITE_DEFAULT_LON,
  -46.7939
)

export const DEFAULT_LOCATION_LABEL =
  import.meta.env.VITE_DEFAULT_LOCATION ?? 'Osasco, SP'

export const API_USER_ID = DEFAULT_USER_ID

/** Grupo do experimento A/B (vazio = atribuição determinística pelo backend). */
export const DEFAULT_AB_GROUP =
  (import.meta.env.VITE_AB_GROUP as ABGroup) ?? ''

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function isUuid(value: string | undefined | null): value is string {
  return !!value && UUID_PATTERN.test(value)
}

/**
 * Deriva o turno a partir do horário de Brasília (UTC-3).
 * O backend não modela fuso no navegador, então usamos o offset fixo do seed.
 */
export function getCurrentTurno(date: Date = new Date()): Turno {
  const hour = (date.getUTCHours() - 3 + 24) % 24

  if (hour >= 5 && hour < 12) return 'manha'
  if (hour >= 12 && hour < 18) return 'tarde'
  if (hour >= 18) return 'noite'
  return 'madrugada'
}

/** Retorna o grupo do experimento A/B configurado via env (ou vazio para deixar o backend decidir). */
export function getABGroup(): ABGroup {
  return DEFAULT_AB_GROUP
}
