import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, searchNearbyRestaurants } from '@/lib/api'
import { useNearbyRestaurants } from '@/hooks/useNearbyRestaurants'
import { useLocationStore } from '@/store/locationStore'
import type { OsmRestaurant } from '@/types'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, searchNearbyRestaurants: vi.fn() }
})

const mockSearch = vi.mocked(searchNearbyRestaurants)

const place: OsmRestaurant = {
  osm_id: 123456789,
  osm_type: 'node',
  name: 'Cantina da Praça',
  latitude: -23.5227,
  longitude: -46.1878,
  category: 'restaurant',
  cuisine: 'italian',
  address: {
    street: 'Rua Teste',
    number: '100',
    city: 'Mogi das Cruzes',
    postcode: null,
  },
  phone: null,
  website: null,
  opening_hours: null,
  osm_url: 'https://www.openstreetmap.org/node/123456789',
  distance_km: 0.42,
}

beforeEach(() => {
  mockSearch.mockReset()
  useLocationStore.setState({
    lat: -23.5227,
    lon: -46.1878,
    label: 'Mogi das Cruzes',
  })
})

describe('useNearbyRestaurants', () => {
  it('carrega restaurantes do OSM para a localização atual', async () => {
    mockSearch.mockResolvedValue({
      source: 'OpenStreetMap',
      count: 1,
      restaurants: [place],
    })

    const { result } = renderHook(() => useNearbyRestaurants())

    expect(result.current.loading).toBe(true)

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.restaurants).toEqual([place])
    expect(result.current.source).toBe('OpenStreetMap')
    expect(result.current.error).toBeNull()
    expect(mockSearch).toHaveBeenCalledWith({
      lat: -23.5227,
      lon: -46.1878,
      radius: 3000,
      category: undefined,
    })
  })

  it('encaminha a categoria selecionada', async () => {
    mockSearch.mockResolvedValue({
      source: 'OpenStreetMap',
      count: 0,
      restaurants: [],
    })

    const { result } = renderHook(() =>
      useNearbyRestaurants({ category: 'cafe' })
    )

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(mockSearch).toHaveBeenCalledWith({
      lat: -23.5227,
      lon: -46.1878,
      radius: 3000,
      category: 'cafe',
    })
  })

  it('degrada com mensagem amigável em rate limit', async () => {
    mockSearch.mockRejectedValue(new ApiError(503, 'limite'))

    const { result } = renderHook(() => useNearbyRestaurants())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.restaurants).toEqual([])
    expect(result.current.error).toBe(
      'Serviço de restaurantes do OpenStreetMap ocupado. Tente novamente em instantes.'
    )
  })

  it('degrada com mensagem amigável em timeout', async () => {
    mockSearch.mockRejectedValue(new ApiError(504, 'timeout'))

    const { result } = renderHook(() => useNearbyRestaurants())

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.error).toBe(
      'A consulta ao OpenStreetMap demorou demais. Tente novamente.'
    )
  })
})
