import type { AccountUser } from '@/lib/accountApi'

/** Chaves nativas usadas para persistir a sessão no navegador. */
export const AUTH_TOKEN_KEY = '@FoodFlow:token'
export const AUTH_USER_KEY = '@FoodFlow:user'

export interface StoredSession {
  token: string
  user: AccountUser
  isDemo: boolean
}

function hasLocalStorage() {
  return (
    typeof window !== 'undefined' &&
    typeof window.localStorage !== 'undefined'
  )
}

/** Tokens criados pelo fallback local (backend sem rotas de autenticação). */
export function isDemoToken(token: string | null | undefined) {
  return Boolean(token && token.startsWith('demo-token-'))
}

function isAccountUser(value: unknown): value is AccountUser {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    typeof (value as AccountUser).id === 'string'
  )
}

/**
 * Lê a sessão das chaves explícitas `@FoodFlow:token` e `@FoodFlow:user`.
 * Retorna `null` quando não há sessão válida armazenada.
 */
export function readStoredSession(): StoredSession | null {
  if (!hasLocalStorage()) return null

  try {
    const token = window.localStorage.getItem(AUTH_TOKEN_KEY)
    if (!token) return null

    const rawUser = window.localStorage.getItem(AUTH_USER_KEY)
    if (!rawUser) return null

    const user: unknown = JSON.parse(rawUser)
    if (!isAccountUser(user)) return null

    return { token, user, isDemo: isDemoToken(token) }
  } catch {
    return null
  }
}

export function writeStoredSession(token: string, user: AccountUser) {
  if (!hasLocalStorage()) return

  try {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token)
    window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
  } catch {
    // Armazenamento indisponível (modo privado/cota cheia): a sessão segue em memória.
  }
}

export function clearStoredSession() {
  if (!hasLocalStorage()) return

  try {
    window.localStorage.removeItem(AUTH_TOKEN_KEY)
    window.localStorage.removeItem(AUTH_USER_KEY)
  } catch {
    // Nada a fazer se o armazenamento estiver indisponível.
  }
}
