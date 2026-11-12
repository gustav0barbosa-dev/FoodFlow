import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OsmRestaurantCard } from '@/components/restaurant/OsmRestaurantCard'
import type { OsmRestaurant } from '@/types'

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
  phone: '+55 11 99999-0000',
  website: 'https://exemplo.test',
  opening_hours: 'Mo-Su 11:00-23:00',
  osm_url: 'https://www.openstreetmap.org/node/123456789',
  distance_km: 0.42,
}

describe('OsmRestaurantCard', () => {
  it('mostra dados básicos e aciona a seleção', () => {
    const onSelect = vi.fn()

    render(
      <OsmRestaurantCard restaurant={restaurant} onSelect={onSelect} />
    )

    expect(screen.getByText('Cantina da Praça')).toBeTruthy()
    expect(screen.getByText('Restaurante · italian')).toBeTruthy()
    expect(screen.getByText('Rua Teste, 100 · Mogi das Cruzes')).toBeTruthy()
    expect(screen.getByText('0.4 km')).toBeTruthy()

    fireEvent.click(
      screen.getByRole('button', {
        name: /Ver detalhes de Cantina da Praça/,
      })
    )
    expect(onSelect).toHaveBeenCalledWith(restaurant)
  })

  it('mostra contatos e link do OSM quando selecionado', () => {
    const onSelect = vi.fn()

    render(
      <OsmRestaurantCard
        restaurant={restaurant}
        selected
        onSelect={onSelect}
      />
    )

    expect(
      screen.getByRole('link', { name: /\+55 11 99999-0000/ })
    ).toBeTruthy()
    expect(
      screen
        .getByRole('link', { name: /exemplo\.test/ })
        .getAttribute('href')
    ).toBe('https://exemplo.test')
    expect(screen.getByText('Mo-Su 11:00-23:00')).toBeTruthy()

    const osmLink = screen.getByRole('link', {
      name: /Ver no OpenStreetMap/,
    })
    expect(osmLink.getAttribute('href')).toBe(
      'https://www.openstreetmap.org/node/123456789'
    )
  })

  it('avisa quando não há contato nem horário cadastrados', () => {
    render(
      <OsmRestaurantCard
        restaurant={{
          ...restaurant,
          phone: null,
          website: null,
          opening_hours: null,
        }}
        selected
        onSelect={vi.fn()}
      />
    )

    expect(
      screen.getByText(/não cadastrados no OpenStreetMap/)
    ).toBeTruthy()
  })

  it('destaca o termo buscado no nome', () => {
    render(
      <OsmRestaurantCard
        restaurant={restaurant}
        query="praça"
        onSelect={vi.fn()}
      />
    )

    expect(screen.getByText('Praça').tagName).toBe('MARK')
  })
})
