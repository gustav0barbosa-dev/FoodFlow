import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { restaurants } from '@/data/mockData'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'

const restaurant = restaurants.find((item) => item.id === 'r1')!

function renderCard(query: string) {
  return render(
    <MemoryRouter>
      <RestaurantCompactCard restaurant={restaurant} query={query} />
    </MemoryRouter>
  )
}

describe('RestaurantCompactCard', () => {
  it('mostra os pratos correspondentes com destaque', () => {
    renderCard('feijoada')

    expect(screen.getByText('Feijoada').tagName).toBe('MARK')
    expect(screen.getByText(/Pratos:/)).toBeTruthy()
  })

  it('não mostra a linha de pratos sem busca', () => {
    renderCard('')

    expect(screen.queryByText(/Pratos:/)).toBeNull()
    expect(screen.getByText(restaurant.name)).toBeTruthy()
  })
})
