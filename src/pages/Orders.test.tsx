import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Orders } from '@/pages/Orders'
import { useOrdersStore } from '@/store/ordersStore'
import type { Order } from '@/store/ordersStore'

function seedOrders(orders: Order[]) {
  useOrdersStore.setState({ orders })
}

function renderOrders() {
  return render(
    <MemoryRouter initialEntries={['/pedidos']}>
      <Orders />
    </MemoryRouter>
  )
}

function buildOrder(overrides: Partial<Order> = {}): Order {
  return {
    id: 'o1',
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    itemCount: 1,
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    status: 'Em preparo',
    createdAt: '2026-11-08T12:00:00.000Z',
    ...overrides,
  }
}

function setStatusFilter(value: string) {
  const select = screen.getByLabelText('Filtrar por status')
  fireEvent.change(select, { target: { value } })
}

describe('Orders filter by status', () => {
  it('mostra todos os pedidos quando o filtro é Todos', () => {
    seedOrders([
      buildOrder({ id: 'o1', status: 'Em preparo' }),
      buildOrder({ id: 'o2', status: 'Entregue' }),
      buildOrder({ id: 'o3', status: 'Saiu para entrega' }),
    ])

    renderOrders()

    expect(screen.getByText(/3 pedidos/)).toBeTruthy()
    expect(screen.getAllByText('Sabor da Vila')).toHaveLength(3)
  })

  it('mostra apenas entregues ao selecionar o filtro', () => {
    seedOrders([
      buildOrder({ id: 'o1', status: 'Em preparo' }),
      buildOrder({ id: 'o2', status: 'Entregue' }),
      buildOrder({ id: 'o3', status: 'Entregue' }),
    ])

    renderOrders()

    setStatusFilter('entregues')

    expect(screen.getByText(/2 pedidos/)).toBeTruthy()
    expect(screen.queryByText(/3 pedidos/)).toBeNull()
  })

  it('mostra apenas em andamento ao selecionar o filtro', () => {
    seedOrders([
      buildOrder({ id: 'o1', status: 'Em preparo' }),
      buildOrder({ id: 'o2', status: 'Entregue' }),
    ])

    renderOrders()

    setStatusFilter('andamento')

    expect(screen.getByText(/1 pedido/)).toBeTruthy()
  })

  it('volta a mostrar todos ao selecionar Todos novamente', () => {
    seedOrders([
      buildOrder({ id: 'o1', status: 'Em preparo' }),
      buildOrder({ id: 'o2', status: 'Entregue' }),
    ])

    renderOrders()

    setStatusFilter('andamento')
    expect(screen.getByText(/1 pedido/)).toBeTruthy()

    setStatusFilter('todos')
    expect(screen.getByText(/2 pedidos/)).toBeTruthy()
  })
})
