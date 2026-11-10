import type { ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export function FullScreenLoader() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex h-full min-h-[60vh] w-full items-center justify-center bg-surface-muted"
    >
      <Loader2
        size={36}
        className="animate-spin text-primary"
        aria-hidden="true"
      />
      <span className="sr-only">Carregando…</span>
    </div>
  )
}

/** Bloqueia o acesso até que exista uma sessão válida. */
export function PrivateRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullScreenLoader />

  if (!isAuthenticated) {
    return <Navigate to="/" replace state={{ from: location }} />
  }

  return <>{children}</>
}

/** Evita que usuários logados vejam novamente boas-vindas/cadastro. */
export function GuestRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <FullScreenLoader />

  if (isAuthenticated) {
    return <Navigate to="/home" replace />
  }

  return <>{children}</>
}
