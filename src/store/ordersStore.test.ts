import { describe, expect, it } from 'vitest'
import {
  nextOrderStatus,
  useOrdersStore,
  type NewOrderInput,
} from '@/store/ordersStore'

function buildOrder(overrides: Partial<NewOrderInput> = {}): NewOrderInput {
  return {
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    address: 'R. das Flores, 123 — Osasco, SP',
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
    expect(order.address).toBe('R. das Flores, 123 — Osasco, SP')
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

  it('avança o status até entregue e para no fim da fila', () => {
    const { addOrder, advanceOrderStatus } = useOrdersStore.getState()
    const order = addOrder(buildOrder())

    expect(advanceOrderStatus(order.id)?.status).toBe('Saiu para entrega')
    expect(advanceOrderStatus(order.id)?.status).toBe('Entregue')
    expect(advanceOrderStatus(order.id)?.status).toBe('Entregue')
    expect(useOrdersStore.getState().orders[0].status).toBe('Entregue')
  })

  it('retorna undefined ao avançar um pedido inexistente', () => {
    expect(useOrdersStore.getState().advanceOrderStatus('inexistente')).toBeUndefined()
  })
})

describe('nextOrderStatus', () => {
  it('segue a ordem de preparo, entrega e conclusão', () => {
    expect(nextOrderStatus('Em preparo')).toBe('Saiu para entrega')
    expect(nextOrderStatus('Saiu para entrega')).toBe('Entregue')
    expect(nextOrderStatus('Entregue')).toBeNull()
  })
})
