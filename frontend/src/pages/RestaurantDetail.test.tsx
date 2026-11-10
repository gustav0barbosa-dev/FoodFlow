import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RestaurantDetail } from '@/pages/RestaurantDetail'
import { resetCatalogStore } from '@/store/catalogStore'
import { useReviewsStore } from '@/store/reviewsStore'
import type { ApiRestaurantDetail } from '@/lib/api'

const API_ID = 'f2d033eb-6ff6-5b74-aac4-b7fcb527cdc0'

const { getRestaurantMock, searchRestaurantsMock } = vi.hoisted(() => ({
  getRestaurantMock: vi.fn(),
  searchRestaurantsMock: vi.fn(),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    getRestaurant: getRestaurantMock,
    searchRestaurants: searchRestaurantsMock,
  }
})

const apiDetail: ApiRestaurantDetail = {
  id: API_ID,
  name: 'Sabor da Vila',
  description: 'Melhor brasileira de Osasco',
  phone: '+55 11 99999-0000',
  address: 'Av. dos Autonomistas, 1400 — Osasco, SP',
  distance_km: null,
  categories: ['Brasileira'],
  average_rating: 4.7,
  review_count: 3,
  delivery_fee: 5.99,
  delivery_time_min: 25,
  delivery_time_max: 35,
  image_url: null,
  reviews: [],
}

function renderDetail(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/restaurante/${id}`]}>
      <Routes>
        <Route path="/restaurante/:id" element={<RestaurantDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  resetCatalogStore()
  useReviewsStore.setState({
    reviews: [
      {
        id: 'local-review',
        restaurantId: 'r1',
        userName: 'Ana Souza',
        rating: 5,
        date: '2026-11-10T00:00:00.000Z',
        comment: 'Muito bom!',
      },
    ],
  })
  searchRestaurantsMock.mockRejectedValue(new Error('offline'))
  getRestaurantMock.mockResolvedValue(apiDetail)
})

describe('RestaurantDetail', () => {
  it('renderiza o detalhe sem entrar em loop infinito de reviews', async () => {
    renderDetail('r1')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sabor da Vila' })
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Avaliações' }))
    expect(await screen.findAllByText('Muito bom!')).toHaveLength(2)
  })

  it('responde um ID legado desconhecido com estado vazio, sem loading infinito', async () => {
    renderDetail('9')

    expect(
      await screen.findByText('Restaurante não encontrado')
    ).toBeTruthy()
    expect(screen.queryByText('Carregando…')).toBeNull()
  })

  it('busca o detalhe na API quando o ID é um UUID', async () => {
    renderDetail(API_ID)

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sabor da Vila' })
    ).toBeTruthy()
    expect(getRestaurantMock).toHaveBeenCalledWith(API_ID)
  })
})
