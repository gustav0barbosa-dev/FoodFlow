import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { restaurants } from '@/data/mockData'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'

const r1 = restaurants.find((item) => item.id === 'r1')!
const r7 = restaurants.find((item) => item.id === 'r7')!

function renderCard(restaurant: (typeof restaurants)[number], query: string) {
  return render(
    <MemoryRouter>
      <RestaurantCompactCard restaurant={restaurant} query={query} />
    </MemoryRouter>
  )
}

describe('RestaurantCompactCard', () => {
  it('mostra os pratos correspondentes com destaque', () => {
    renderCard(r1, 'feijoada')

    expect(screen.getByText('Feijoada').tagName).toBe('MARK')
    expect(screen.getByText(/Pratos:/)).toBeTruthy()
  })

  it('destaca o prato correspondente pela descrição', () => {
    renderCard(r1, 'vinagrete')

    expect(screen.getByText('vinagrete').tagName).toBe('MARK')
    expect(screen.getByText(/Pratos:/)).toBeTruthy()
  })

  it('destaca a descrição quando o nome não corresponde', () => {
    renderCard(r7, 'folhado')

    expect(screen.getByText('Croissant de Manteiga').tagName).not.toBe('MARK')
    expect(screen.getByText(/Pratos:/)).toBeTruthy()
  })

  it('não mostra a linha de pratos sem busca', () => {
    renderCard(r1, '')

    expect(screen.queryByText(/Pratos:/)).toBeNull()
    expect(screen.getByText(r1.name)).toBeTruthy()
  })
})
