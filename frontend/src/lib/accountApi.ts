/**
 * Cliente das rotas de conta.
 *
 * ATENÇÃO: o backend atual do FoodFlow (v0.2.0) NÃO expõe rotas de
 * autenticação/usuário. As rotas abaixo seguem o contrato pedido para o
 * produto e ficam centralizadas aqui para facilitar a troca quando o backend
 * implementá-las:
 *
 * - POST /auth/register            (TODO: confirmar rota e payload com backend)
 * - POST /auth/login               (TODO: confirmar rota e payload com backend)
 * - GET  /users/me                 (TODO: confirmar rota e payload com backend)
 * - PATCH /users/me                (TODO: confirmar rota e payload com backend)
 * - PATCH /users/me/address        (TODO: confirmar rota e payload com backend)
 *
 * Enquanto isso, o wizard usa um fallback local transparente (modo demonstração).
 */

import type { AddressFields, Coordinates } from '@/lib/address'
import { API_BASE_URL } from '@/lib/config'

export interface AccountUser {
  id: string
  email: string
  name?: string
  phone?: string
  address?: AddressFields
  coordinates?: Coordinates | null
}

export interface AuthSession {
  token: string | null
  user: AccountUser
}

export class AccountApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'AccountApiError'
    this.status = status
    Object.setPrototypeOf(this, AccountApiError.prototype)
  }
}

const REQUEST_TIMEOUT_MS = 8000

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  token?: string | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : undefined
}

function extractDetail(body: unknown, fallback: string) {
  if (!isRecord(body)) return fallback

  const detail = body.detail

  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const firstMessage = detail.find(
      (item) => isRecord(item) && typeof item.msg === 'string'
    )
    if (isRecord(firstMessage) && typeof firstMessage.msg === 'string') {
      return firstMessage.msg
    }
  }

  return readString(body.message) ?? fallback
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (typeof fetch !== 'function') {
    throw new AccountApiError(0, 'API indisponível')
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const headers = new Headers({ Accept: 'application/json' })
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    if (options.token) headers.set('Authorization', `Bearer ${options.token}`)

    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    })

    if (!response.ok) {
      let detail = `Erro ${response.status} ao salvar seus dados`
      try {
        detail = extractDetail(await response.json(), detail)
      } catch {
        // A resposta pode não ser JSON; mantém a mensagem padrão.
      }
      throw new AccountApiError(response.status, detail)
    }

    if (response.status === 204) return undefined as T

    try {
      return (await response.json()) as T
    } catch {
      return undefined as T
    }
  } catch (error) {
    if (error instanceof AccountApiError) throw error
    throw new AccountApiError(0, 'Não foi possível conectar ao servidor')
  } finally {
    clearTimeout(timeout)
  }
}

export interface RegisterPayload {
  email: string
  password: string
}

export interface AddressPayload extends AddressFields {
  latitude?: number
  longitude?: number
}

/**
 * Normaliza as diferentes formas de resposta do backend:
 * `{ id, email }`, `{ user: {...} }` ou `{ data: { user: {...} } }`.
 */
function parseAccountUser(data: unknown, fallbackEmail = ''): AccountUser {
  const root = isRecord(data) ? data : {}
  const nested = isRecord(root.data) ? root.data : {}
  const candidate = isRecord(root.user)
    ? root.user
    : isRecord(nested.user)
      ? nested.user
      : root

  const user: AccountUser = {
    id: readString(candidate.id) ?? '',
    email: readString(candidate.email) ?? fallbackEmail,
  }

  const name = readString(candidate.name)
  if (name) user.name = name

  const phone = readString(candidate.phone)
  if (phone) user.phone = phone

  if (isRecord(candidate.address)) {
    user.address = candidate.address as unknown as AddressFields
  }

  if (candidate.coordinates === null) {
    user.coordinates = null
  } else if (isRecord(candidate.coordinates)) {
    const lat =
      typeof candidate.coordinates.lat === 'number'
        ? candidate.coordinates.lat
        : typeof candidate.coordinates.latitude === 'number'
          ? candidate.coordinates.latitude
          : undefined
    const lon =
      typeof candidate.coordinates.lon === 'number'
        ? candidate.coordinates.lon
        : typeof candidate.coordinates.longitude === 'number'
          ? candidate.coordinates.longitude
          : undefined

    if (lat !== undefined && lon !== undefined) {
      user.coordinates = { lat, lon }
    }
  }

  return user
}

function parseAuthSession(data: unknown, fallbackEmail: string): AuthSession {
  const root = isRecord(data) ? data : {}
  const nested = isRecord(root.data) ? root.data : {}

  const token =
    readString(root.token) ??
    readString(root.access_token) ??
    readString(nested.token) ??
    readString(nested.access_token) ??
    null

  return {
    token,
    user: parseAccountUser(data, fallbackEmail),
  }
}

/** Cria a conta. O token pode vir como `token`, `access_token` ou `data.token`. */
export async function registerUser(payload: RegisterPayload): Promise<AuthSession> {
  const data = await request<unknown>('/auth/register', {
    method: 'POST',
    body: payload,
  })

  return parseAuthSession(data, payload.email)
}

/** Autentica uma conta existente. O token segue o mesmo contrato do cadastro. */
export async function loginUser(payload: RegisterPayload): Promise<AuthSession> {
  const data = await request<unknown>('/auth/login', {
    method: 'POST',
    body: payload,
  })

  return parseAuthSession(data, payload.email)
}

/** Valida o token salvo e devolve os dados atuais do usuário. */
export async function getCurrentUser(token: string): Promise<AccountUser> {
  const data = await request<unknown>('/users/me', { token })
  return parseAccountUser(data)
}

/** TODO: confirmar com o backend se o telefone deve ir formatado ou só com dígitos. */
export async function updateUserPhone(token: string | null, phone: string) {
  return request<unknown>('/users/me', {
    method: 'PATCH',
    token,
    body: { phone },
  })
}

/** Envia o endereço estruturado e, quando houver, as coordenadas capturadas. */
export async function updateUserAddress(
  token: string | null,
  payload: AddressPayload
) {
  return request<unknown>('/users/me/address', {
    method: 'PATCH',
    token,
    body: payload,
  })
}

/**
 * O backend atual não tem rota de cadastro. Nesses casos, o frontend continua
 * o fluxo com uma sessão local para permitir testar toda a experiência.
 */
export function isAccountApiUnavailable(error: unknown) {
  return (
    error instanceof AccountApiError &&
    [0, 404, 405, 501].includes(error.status)
  )
}

function nameFromEmail(email: string) {
  const localPart = email.split('@')[0] ?? ''
  const words = localPart
    .replace(/[._-]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)

  if (words.length === 0) return 'Cliente FoodFlow'

  return words
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

export function createDemoSession(email: string): AuthSession {
  const randomId =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

  return {
    token: `demo-token-${randomId}`,
    user: {
      id: `demo-${randomId}`,
      email,
      name: nameFromEmail(email),
    },
  }
}

export function accountErrorMessage(error: unknown) {
  if (error instanceof AccountApiError) {
    if (error.status === 409) {
      return 'Este e-mail já está cadastrado. Use outro e-mail ou faça login.'
    }
    if (error.status === 401) {
      return 'Sua sessão expirou. Volte à primeira etapa e tente novamente.'
    }
    if (error.status === 422) {
      return 'Confira os dados informados e tente novamente.'
    }
    return error.message
  }

  return 'Não foi possível salvar seus dados. Tente novamente.'
}
