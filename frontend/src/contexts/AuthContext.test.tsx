import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from '@/contexts/AuthProvider'
import { useAuth } from '@/contexts/AuthContext'
import {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  writeStoredSession,
} from '@/lib/authStorage'

let fetchMock: ReturnType<typeof vi.fn>

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AuthContext', () => {
  it('restaura uma sessão demo salva sem consultar o backend', async () => {
    writeStoredSession('demo-token-123', {
      id: 'demo-1',
      email: 'ana@exemplo.com',
      name: 'Ana Souza',
    })

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.isDemo).toBe(true)
    expect(result.current.user?.name).toBe('Ana Souza')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('valida o token real em GET /users/me e atualiza o usuário', async () => {
    writeStoredSession('jwt-valido', {
      id: 'user-1',
      email: 'ana@exemplo.com',
      name: 'Ana',
    })

    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'user-1',
          email: 'ana@exemplo.com',
          name: 'Ana Souza',
          phone: '11999998888',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/users/me')
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user?.name).toBe('Ana Souza')
    expect(result.current.user?.phone).toBe('11999998888')
  })

  it('faz logout automático quando o backend responde 401', async () => {
    writeStoredSession('jwt-expirado', {
      id: 'user-1',
      email: 'ana@exemplo.com',
    })

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Não autorizado' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(AUTH_USER_KEY)).toBeNull()
  })

  it('login persiste a sessão e logout limpa tudo', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      result.current.login('demo-token-abc', {
        id: 'demo-2',
        email: 'bia@exemplo.com',
        name: 'Bia',
      })
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('demo-token-abc')
    expect(localStorage.getItem(AUTH_USER_KEY)).toContain('Bia')

    act(() => {
      result.current.logout()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBeNull()
    expect(localStorage.getItem(AUTH_USER_KEY)).toBeNull()
  })
})
