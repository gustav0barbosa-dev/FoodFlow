import { createContext, useContext } from 'react'
import type { AccountUser } from '@/lib/accountApi'

export interface LoginOptions {
  /** Sessão local enquanto o backend não oferece autenticação. */
  demo?: boolean
}

export interface AuthContextValue {
  user: AccountUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  isDemo: boolean
  login: (
    token: string | null,
    userData: AccountUser,
    options?: LoginOptions
  ) => void
  logout: () => void
  updateUser: (userData: Partial<AccountUser>) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth deve ser usado dentro de um AuthProvider')
  }

  return context
}
