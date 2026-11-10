import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AccountApiError,
  isAccountApiUnavailable,
  registerUser,
  updateUserAddress,
} from '@/lib/accountApi'

let fetchMock: ReturnType<typeof vi.fn>

function jsonResponse(status: number, body: unknown = {}) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('accountApi', () => {
  it('envia o cadastro e encontra o token na resposta', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(201, {
        access_token: 'jwt-123',
        user: { id: 'u1', email: 'ana@exemplo.com', name: 'Ana' },
      })
    )

    const session = await registerUser({
      email: 'ana@exemplo.com',
      password: '12345678',
    })

    expect(session.token).toBe('jwt-123')
    expect(session.user).toMatchObject({
      id: 'u1',
      email: 'ana@exemplo.com',
      name: 'Ana',
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/auth/register')
    expect(init.method).toBe('POST')
    expect(String(init.body)).toContain('"email":"ana@exemplo.com"')
  })

  it('envia o endereço com Bearer token', async () => {
    fetchMock.mockResolvedValue(jsonResponse(204))

    await updateUserAddress('jwt-123', {
      cep: '06110000',
      street: 'Av. dos Autonomistas',
      number: '1400',
      complement: '',
      neighborhood: 'Centro',
      city: 'Osasco',
      state: 'SP',
      latitude: -23.53,
      longitude: -46.79,
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const headers = new Headers(init.headers)

    expect(url).toContain('/users/me/address')
    expect(init.method).toBe('PATCH')
    expect(headers.get('Authorization')).toBe('Bearer jwt-123')

    const body = JSON.parse(String(init.body)) as Record<string, unknown>
    expect(body.cep).toBe('06110000')
    expect(body.latitude).toBe(-23.53)
  })

  it('classifica 404 como endpoint indisponível para o fallback local', async () => {
    fetchMock.mockResolvedValue(jsonResponse(404, { detail: 'Not Found' }))

    const error = await registerUser({
      email: 'ana@exemplo.com',
      password: '12345678',
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(AccountApiError)
    expect(isAccountApiUnavailable(error)).toBe(true)
  })

  it('não trata 409 (e-mail duplicado) como indisponível', async () => {
    fetchMock.mockResolvedValue(jsonResponse(409, { detail: 'E-mail já existe' }))

    const error = await registerUser({
      email: 'ana@exemplo.com',
      password: '12345678',
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(AccountApiError)
    expect(isAccountApiUnavailable(error)).toBe(false)
  })
})
