import { describe, expect, it } from 'vitest'
import type { Order } from '@/store/ordersStore'
import {
  formatOrderDate,
  groupOrderItems,
  orderRestaurantLabel,
} from '@/lib/orders'

const multiRestaurantOrder: Order = {
  id: 'o1',
  restaurantNames: ['Sabor da Vila', 'Verde Vivo — Saudável'],
  items: [
    { id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 },
    { id: 'r2-m1', name: 'Bowl Proteico', price: 32.5, quantity: 2 },
  ],
  itemCount: 3,
  subtotal: 107.9,
  deliveryFee: 5.99,
  total: 113.89,
  status: 'Entregue',
  createdAt: '2026-10-28T19:30:00',
}

describe('groupOrderItems', () => {
  it('agrupa itens pelo restaurante de origem', () => {
    const groups = groupOrderItems(multiRestaurantOrder)

    expect(groups).toHaveLength(2)
    expect(groups[0]).toMatchObject({
      restaurantId: 'r1',
      restaurantName: 'Sabor da Vila',
    })
    expect(groups[0].items).toHaveLength(1)
    expect(groups[1]).toMatchObject({
      restaurantId: 'r2',
      restaurantName: 'Verde Vivo — Saudável',
    })
    expect(groups[1].items[0].quantity).toBe(2)
  })
})

describe('orderRestaurantLabel', () => {
  it('usa o nome único quando há um restaurante', () => {
    expect(
      orderRestaurantLabel({
        ...multiRestaurantOrder,
        restaurantNames: ['Sabor da Vila'],
      })
    ).toBe('Sabor da Vila')
  })

  it('resume pedidos com múltiplos restaurantes', () => {
    expect(orderRestaurantLabel(multiRestaurantOrder)).toBe(
      'Sabor da Vila + 1 restaurante'
    )
  })
})

describe('formatOrderDate', () => {
  it('formata a data em pt-BR', () => {
    expect(formatOrderDate('2026-10-28T19:30:00')).toMatch(
      /^\d{2}\/\d{2}\/\d{4}, \d{2}:\d{2}$/
    )
  })
})
