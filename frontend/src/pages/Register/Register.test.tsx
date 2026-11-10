import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthProvider'
import { Register } from '@/pages/Register'

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Not Found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    })
  )
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderRegister() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/cadastro']}>
        <Routes>
          <Route path="/cadastro" element={<Register />} />
          <Route path="/home" element={<div>Home logada</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>
  )
}

describe('cadastro em etapas', () => {
  it('valida cada etapa, usa o fallback local e finaliza na home', async () => {
    renderRegister()

    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('Informe seu e-mail')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('E-mail'), {
      target: { value: 'ana.souza@exemplo.com' },
    })
    fireEvent.change(screen.getByLabelText('Senha'), {
      target: { value: '12345678' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(await screen.findByText('Qual é o seu telefone?')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Telefone com DDD'), {
      target: { value: '11999998888' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(
      await screen.findByText('Onde você quer receber seus pedidos?')
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Digitar endereço' }))
    fireEvent.change(screen.getByLabelText('CEP'), {
      target: { value: '06110000' },
    })
    fireEvent.change(screen.getByLabelText('Rua / Avenida'), {
      target: { value: 'Av. dos Autonomistas' },
    })
    fireEvent.change(screen.getByLabelText('Número'), {
      target: { value: '1400' },
    })
    fireEvent.change(screen.getByLabelText('Bairro'), {
      target: { value: 'Centro' },
    })
    fireEvent.change(screen.getByLabelText('Cidade'), {
      target: { value: 'Osasco' },
    })
    fireEvent.change(screen.getByLabelText('Estado'), {
      target: { value: 'SP' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Finalizar cadastro' }))

    expect(await screen.findByText('Home logada')).toBeTruthy()
  })
})
