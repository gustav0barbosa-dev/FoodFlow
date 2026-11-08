import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { Home } from '@/pages/Home'
import { useCartStore } from '@/store/cartStore'
import { useHomeFiltersStore } from '@/store/homeFiltersStore'

beforeEach(() => {
  localStorage.clear()
  useCartStore.setState({ lines: [] })
  useHomeFiltersStore.setState({ filter: 'Todos', category: null })
})

describe('Home carregar mais', () => {
  it('inicializa com 3 restaurantes e carrega mais ao clicar', async () => {
    render(
      <MemoryRouter initialEntries={['/home']}>
        <Home />
      </MemoryRouter>
    )

    const cards = document.querySelectorAll('a[href^="/restaurante/"]')
    expect(cards.length).toBeLessThanOrEqual(3)

    const carregarMais = await screen.findAllByRole('button', {
      name: /Carregar mais/,
    })
    fireEvent.click(carregarMais[0])

    const cardsAfter = document.querySelectorAll('a[href^="/restaurante/"]')
    expect(cardsAfter.length).toBeGreaterThan(cards.length)
  })
})
