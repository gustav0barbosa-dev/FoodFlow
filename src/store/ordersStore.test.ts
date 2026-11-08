import { describe, expect, it } from 'vitest'
import { useOrdersStore, type NewOrderInput } from '@/store/ordersStore'

function buildOrder(overrides: Partial<NewOrderInput> = {}): NewOrderInput {
  return {
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    ...overrides,
  }
}

describe('ordersStore', () => {
  it('cria pedido em preparo com contagem e total corretos', () => {
    const order = useOrdersStore.getState().addOrder(
      buildOrder({
        items: [
          { id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 2 },
        ],
        subtotal: 85.8,
        total: 91.79,
      })
    )

    expect(order.status).toBe('Em preparo')
    expect(order.itemCount).toBe(2)
    expect(order.subtotal).toBe(85.8)
    expect(order.deliveryFee).toBe(5.99)
    expect(order.total).toBe(91.79)
  })

  it('coloca o pedido mais recente no topo', () => {
    const { addOrder } = useOrdersStore.getState()

    const first = addOrder(buildOrder())
    const second = addOrder(buildOrder({ restaurantNames: ['Verde Vivo'] }))

    const { orders } = useOrdersStore.getState()
    expect(orders[0].id).toBe(second.id)
    expect(orders[1].id).toBe(first.id)
  })

  it('gera identificadores únicos em sequência', () => {
    const { addOrder } = useOrdersStore.getState()

    const ids = new Set([
      addOrder(buildOrder()).id,
      addOrder(buildOrder()).id,
      addOrder(buildOrder()).id,
    ])

    expect(ids.size).toBe(3)
  })
})
