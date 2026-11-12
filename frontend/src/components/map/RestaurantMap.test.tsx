import type { ReactNode } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RestaurantMap } from '@/components/map/RestaurantMap'
import type { OsmRestaurant } from '@/types'

const { setView } = vi.hoisted(() => ({ setView: vi.fn() }))

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="map">{children}</div>
  ),
  TileLayer: ({
    attribution,
    url,
  }: {
    attribution: string
    url: string
  }) => (
    <div
      data-testid="tile-layer"
      data-attribution={attribution}
      data-url={url}
    />
  ),
  CircleMarker: ({
    children,
    eventHandlers,
  }: {
    children: ReactNode
    eventHandlers?: { click?: () => void }
  }) => (
    <button type="button" data-testid="marker" onClick={eventHandlers?.click}>
      {children}
    </button>
  ),
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useMap: () => ({ setView }),
}))

const restaurant: OsmRestaurant = {
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

describe('RestaurantMap', () => {
  it('usa tiles do OSM e renderiza um marcador por restaurante', () => {
    const onSelect = vi.fn()

    render(
      <RestaurantMap
        restaurants={[restaurant]}
        center={{ lat: -23.5227, lon: -46.1878 }}
        selectedKey={null}
        onSelect={onSelect}
      />
    )

    const tile = screen.getByTestId('tile-layer')
    expect(tile.getAttribute('data-url')).toBe(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
    )
    expect(tile.getAttribute('data-attribution')).toContain(
      'OpenStreetMap'
    )

    const markers = screen.getAllByTestId('marker')
    expect(markers).toHaveLength(1)

    fireEvent.click(markers[0])
    expect(onSelect).toHaveBeenCalledWith(restaurant)
  })

  it('centraliza o mapa na localização informada', () => {
    setView.mockClear()

    render(
      <RestaurantMap
        restaurants={[restaurant]}
        center={{ lat: -23.5227, lon: -46.1878 }}
        selectedKey={null}
        onSelect={vi.fn()}
      />
    )

    expect(setView).toHaveBeenCalledWith([-23.5227, -46.1878])
  })
})
