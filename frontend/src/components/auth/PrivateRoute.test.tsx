import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { GuestRoute, PrivateRoute } from '@/components/auth/PrivateRoute'
import { AuthProvider } from '@/contexts/AuthProvider'
import { writeStoredSession } from '@/lib/authStorage'

function renderApp(initialPath: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="/"
            element={
              <GuestRoute>
                <div>Boas-vindas</div>
              </GuestRoute>
            }
          />
          <Route
            path="/home"
            element={
              <PrivateRoute>
                <div>Home protegida</div>
              </PrivateRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </AuthProvider>
  )
}

describe('guards de rota', () => {
  it('manda visitantes para as boas-vindas ao abrir uma rota privada', async () => {
    renderApp('/home')

    expect(await screen.findByText('Boas-vindas')).toBeTruthy()
    expect(screen.queryByText('Home protegida')).toBeNull()
  })

  it('manda usuários logados direto para a home', async () => {
    writeStoredSession('demo-token-guard', {
      id: 'demo-guard',
      email: 'ana@exemplo.com',
      name: 'Ana',
    })

    renderApp('/')

    expect(await screen.findByText('Home protegida')).toBeTruthy()
    expect(screen.queryByText('Boas-vindas')).toBeNull()
  })
})
