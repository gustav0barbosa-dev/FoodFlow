import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RestaurantDetail } from '@/pages/RestaurantDetail'
import { resetCatalogStore } from '@/store/catalogStore'
import { useReviewsStore } from '@/store/reviewsStore'
import type { ApiRestaurantDetail } from '@/lib/api'

const API_ID = 'f2d033eb-6ff6-5b74-aac4-b7fcb527cdc0'

const { getRestaurantMock, getOsmRestaurantMock, searchRestaurantsMock, createInteractionMock } =
  vi.hoisted(() => ({
    getRestaurantMock: vi.fn(),
    getOsmRestaurantMock: vi.fn(),
    searchRestaurantsMock: vi.fn(),
    createInteractionMock: vi.fn(),
  }))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    getRestaurant: getRestaurantMock,
    getOsmRestaurant: getOsmRestaurantMock,
    searchRestaurants: searchRestaurantsMock,
    createInteraction: createInteractionMock,
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

const osmApiDetail: ApiRestaurantDetail = {
  id: API_ID,
  name: 'Cantina da Praça',
  description: null,
  phone: null,
  address: '',
  distance_km: null,
  categories: ['restaurant'],
  average_rating: 0,
  review_count: 0,
  delivery_fee: 0,
  delivery_time_min: 20,
  delivery_time_max: 30,
  image_url: null,
  source: 'osm',
  osm_type: 'node',
  osm_id: 123456789,
  latitude: -23.5227,
  longitude: -46.1878,
  cuisine: 'italian',
  website: null,
  opening_hours: null,
  osm_url: 'https://www.openstreetmap.org/node/123456789',
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

function renderOsmDetail(
  osmType = 'node',
  osmId = 123456789,
  state?: Record<string, unknown>
) {
  return render(
    <MemoryRouter
      initialEntries={[
        {
          pathname: `/restaurante/osm/${osmType}/${osmId}`,
          state,
        },
      ]}
    >
      <Routes>
        <Route
          path="/restaurante/osm/:osmType/:osmId"
          element={<RestaurantDetail />}
        />
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
  getOsmRestaurantMock.mockResolvedValue(osmApiDetail)
  createInteractionMock.mockResolvedValue({ id: 'interaction-1' })
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

  it('abre o detalhe do OSM exibindo somente dados disponíveis', async () => {
    renderOsmDetail()

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Cantina da Praça',
      })
    ).toBeTruthy()

    expect(getOsmRestaurantMock).toHaveBeenCalledWith('node', 123456789)
    expect(screen.getByText('Restaurante · italian')).toBeTruthy()
    expect(screen.getByText('-23.52270, -46.18780')).toBeTruthy()

    // Sem cardápio, avaliações, entrega ou checkout para dados do OSM.
    expect(screen.queryByRole('button', { name: 'Cardápio' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Avaliações' })).toBeNull()
    expect(screen.queryByText(/avaliações/)).toBeNull()
    expect(screen.queryByText(/Ver sacola/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Sobre' })).toBeTruthy()
  })

  it('registra CLICK e VIEW ao abrir detalhes vindos da listagem OSM', async () => {
    createInteractionMock.mockClear()

    renderOsmDetail('node', 123456789, { interaction: 'CLICK' })

    await screen.findByRole('heading', {
      level: 1,
      name: 'Cantina da Praça',
    })

    await waitFor(() => {
      expect(createInteractionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          restaurantId: API_ID,
          interactionType: 'VIEW',
        })
      )
      expect(createInteractionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          restaurantId: API_ID,
          interactionType: 'CLICK',
        })
      )
    })
  })
})
