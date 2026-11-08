import { describe, expect, it } from 'vitest'
import {
  AUTO_ADVANCE_STEP_MS,
  deriveOrderStatus,
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

  it('avança automaticamente o status conforme o tempo decorrido', () => {
    const createdAt = new Date('2026-11-08T12:00:00.000Z').getTime()

    useOrdersStore.setState({
      orders: [
        {
          id: 'auto-1',
          restaurantNames: ['Sabor da Vila'],
          items: [
            { id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 },
          ],
          itemCount: 1,
          subtotal: 42.9,
          deliveryFee: 5.99,
          total: 48.89,
          status: 'Em preparo',
          createdAt: new Date(createdAt).toISOString(),
        },
      ],
    })

    const { syncOrderStatuses } = useOrdersStore.getState()

    expect(syncOrderStatuses(createdAt)).toBe(0)
    expect(useOrdersStore.getState().orders[0].status).toBe('Em preparo')

    expect(syncOrderStatuses(createdAt + AUTO_ADVANCE_STEP_MS)).toBe(1)
    expect(useOrdersStore.getState().orders[0].status).toBe('Saiu para entrega')

    expect(syncOrderStatuses(createdAt + AUTO_ADVANCE_STEP_MS * 2)).toBe(1)
    expect(useOrdersStore.getState().orders[0].status).toBe('Entregue')

    expect(syncOrderStatuses(createdAt + AUTO_ADVANCE_STEP_MS * 10)).toBe(0)
  })

  it('não regride um status avançado manualmente', () => {
    const createdAt = new Date('2026-11-08T12:00:00.000Z').getTime()

    useOrdersStore.setState({
      orders: [
        {
          id: 'auto-2',
          restaurantNames: ['Sabor da Vila'],
          items: [
            { id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 },
          ],
          itemCount: 1,
          subtotal: 42.9,
          deliveryFee: 5.99,
          total: 48.89,
          status: 'Entregue',
          createdAt: new Date(createdAt).toISOString(),
        },
      ],
    })

    expect(
      useOrdersStore.getState().syncOrderStatuses(createdAt + 1_000)
    ).toBe(0)
    expect(useOrdersStore.getState().orders[0].status).toBe('Entregue')
  })
})

describe('nextOrderStatus', () => {
  it('segue a ordem de preparo, entrega e conclusão', () => {
    expect(nextOrderStatus('Em preparo')).toBe('Saiu para entrega')
    expect(nextOrderStatus('Saiu para entrega')).toBe('Entregue')
    expect(nextOrderStatus('Entregue')).toBeNull()
  })
})

describe('deriveOrderStatus', () => {
  const createdAt = '2026-11-08T12:00:00.000Z'
  const base = new Date(createdAt).getTime()

  it('mapeia o tempo decorrido para o fluxo de status', () => {
    expect(deriveOrderStatus(createdAt, base)).toBe('Em preparo')
    expect(deriveOrderStatus(createdAt, base + AUTO_ADVANCE_STEP_MS - 1)).toBe(
      'Em preparo'
    )
    expect(deriveOrderStatus(createdAt, base + AUTO_ADVANCE_STEP_MS)).toBe(
      'Saiu para entrega'
    )
    expect(deriveOrderStatus(createdAt, base + AUTO_ADVANCE_STEP_MS * 2)).toBe(
      'Entregue'
    )
    expect(deriveOrderStatus(createdAt, base + AUTO_ADVANCE_STEP_MS * 50)).toBe(
      'Entregue'
    )
  })

  it('mantém em preparo quando a data é inválida', () => {
    expect(deriveOrderStatus('data-invalida', base)).toBe('Em preparo')
  })
})
