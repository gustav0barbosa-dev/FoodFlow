import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  AccountApiError,
  getCurrentUser,
  type AccountUser,
} from '@/lib/accountApi'
import {
  clearStoredSession,
  isDemoToken,
  readStoredSession,
  writeStoredSession,
} from '@/lib/authStorage'
import { useAuthStore } from '@/store/authStore'
import {
  AuthContext,
  type AuthContextValue,
  type LoginOptions,
} from '@/contexts/AuthContext'

function readInitialLoading() {
  const current = useAuthStore.getState()
  if (current.token) return true

  return Boolean(readStoredSession()?.token)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // O zustand hidrata o localStorage de forma síncrona, então os seletores
  // abaixo já refletem a sessão salva no primeiro render.
  const token = useAuthStore((state) => state.token)
  const user = useAuthStore((state) => state.user)
  const storedDemo = useAuthStore((state) => state.isDemo)
  const isDemo = storedDemo || isDemoToken(token)
  const [isLoading, setIsLoading] = useState(readInitialLoading)

  const login = useCallback(
    (
      nextToken: string | null,
      userData: AccountUser,
      options?: LoginOptions
    ) => {
      if (!nextToken) {
        clearStoredSession()
        useAuthStore.getState().signOut()
        setIsLoading(false)
        return
      }

      const demo = options?.demo ?? isDemoToken(nextToken)

      useAuthStore
        .getState()
        .setSession({ token: nextToken, user: userData }, { demo })
      writeStoredSession(nextToken, userData)
      setIsLoading(false)
    },
    []
  )

  const logout = useCallback(() => {
    clearStoredSession()
    useAuthStore.getState().signOut()
    setIsLoading(false)
  }, [])

  const updateUser = useCallback((userData: Partial<AccountUser>) => {
    const state = useAuthStore.getState()
    if (!state.user) return

    state.updateUser(userData)

    if (state.token) {
      writeStoredSession(state.token, { ...state.user, ...userData })
    }
  }, [])

  // Mantém `@FoodFlow:token` / `@FoodFlow:user` sincronizados com qualquer
  // atualização feita no store (telefone, endereço, etc.).
  useEffect(() => {
    if (token && user) writeStoredSession(token, user)
  }, [token, user])

  // Valida o token salvo uma única vez, ao abrir o app.
  useEffect(() => {
    let cancelled = false

    const current = useAuthStore.getState()
    const stored = readStoredSession()
    const session =
      current.token && current.user
        ? {
            token: current.token,
            user: current.user,
            isDemo: current.isDemo,
          }
        : stored

    if (!session) {
      setIsLoading(false)
      return
    }

    // Migra sessões antigas (persistidas apenas pelo zustand) para as chaves
    // explícitas usadas pelo AuthContext.
    if (!current.token || !current.user) {
      useAuthStore
        .getState()
        .setSession(
          { token: session.token, user: session.user },
          { demo: session.isDemo || isDemoToken(session.token) }
        )
    }

    if (session.isDemo || isDemoToken(session.token)) {
      writeStoredSession(session.token, session.user)
      setIsLoading(false)
      return
    }

    getCurrentUser(session.token)
      .then((freshUser) => {
        if (cancelled) return

        const state = useAuthStore.getState()
        state.updateUser(freshUser)
        writeStoredSession(session.token, { ...session.user, ...freshUser })
        setIsLoading(false)
      })
      .catch((error: unknown) => {
        if (cancelled) return

        // Token inválido/expirado: encerra a sessão automaticamente.
        if (error instanceof AccountApiError && error.status === 401) {
          clearStoredSession()
          useAuthStore.getState().signOut()
        }

        // Falha de rede, timeout ou rota ainda inexistente (404): mantém a
        // sessão local para o app continuar funcionando em modo offline.
        setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(token),
      isLoading,
      isDemo,
      login,
      logout,
      updateUser,
    }),
    [user, token, isLoading, isDemo, login, logout, updateUser]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
