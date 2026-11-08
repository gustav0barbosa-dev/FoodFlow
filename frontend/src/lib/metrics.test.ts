import { describe, expect, it } from 'vitest'
import type { Order } from '@/store/ordersStore'
import { getOrderMetrics } from '@/lib/metrics'

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

describe('getOrderMetrics', () => {
  it('zera as métricas e o favorito quando não há pedidos', () => {
    expect(getOrderMetrics([])).toEqual({
      orderCount: 0,
      totalSpent: 0,
      favoriteRestaurant: null,
    })
  })

  it('soma pedidos e valor total', () => {
    const metrics = getOrderMetrics([
      buildOrder({ id: 'o1', total: 48.89 }),
      buildOrder({ id: 'o2', total: 32.5 }),
    ])

    expect(metrics.orderCount).toBe(2)
    expect(metrics.totalSpent).toBeCloseTo(81.39)
  })

  it('escolhe o restaurante mais frequente no histórico', () => {
    const metrics = getOrderMetrics([
      buildOrder({ id: 'o1', restaurantNames: ['Sabor da Vila'] }),
      buildOrder({ id: 'o2', restaurantNames: ['Sabor da Vila'] }),
      buildOrder({ id: 'o3', restaurantNames: ['Verde Vivo'] }),
    ])

    expect(metrics.favoriteRestaurant).toBe('Sabor da Vila')
  })

  it('desempata pelo nome em ordem alfabética', () => {
    const metrics = getOrderMetrics([
      buildOrder({ id: 'o1', restaurantNames: ['Verde Vivo'] }),
      buildOrder({ id: 'o2', restaurantNames: ['Sabor da Vila'] }),
    ])

    expect(metrics.favoriteRestaurant).toBe('Sabor da Vila')
  })
})
