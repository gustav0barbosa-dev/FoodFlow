import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProfileStats } from '@/components/profile/ProfileStats'
import { useOrdersStore, type Order } from '@/store/ordersStore'

function buildOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: 'o1',
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    itemCount: 1,
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    status: 'Entregue',
    createdAt: '2026-10-28T19:30:00',
    ...overrides,
  }
}

describe('ProfileStats', () => {
  it('mostra pedidos, gasto total e restaurante favorito', () => {
    useOrdersStore.setState({
      orders: [
        buildOrder({ id: 'o1', total: 48.89 }),
        buildOrder({ id: 'o2', total: 32.5 }),
      ],
    })

    render(<ProfileStats />)

    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText(/81,39/)).toBeTruthy()
    expect(screen.getByText('Sabor da Vila')).toBeTruthy()
  })

  it('mostra estado vazio sem pedidos', () => {
    render(<ProfileStats />)

    expect(screen.getByText('0')).toBeTruthy()
    expect(screen.getByText(/0,00/)).toBeTruthy()
    expect(screen.getByText('Sem pedidos ainda')).toBeTruthy()
  })
})
