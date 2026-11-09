import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type OrderStatus = 'Em preparo' | 'Saiu para entrega' | 'Entregue'

export const ORDER_STATUS_FLOW: OrderStatus[] = [
  'Em preparo',
  'Saiu para entrega',
  'Entregue',
]

export function nextOrderStatus(status: OrderStatus): OrderStatus | null {
  const index = ORDER_STATUS_FLOW.indexOf(status)
  if (index === -1 || index === ORDER_STATUS_FLOW.length - 1) return null
  return ORDER_STATUS_FLOW[index + 1]
}

/** Mock time window used to simulate the delivery progression. */
export const AUTO_ADVANCE_STEP_MS = 60_000

export function deriveOrderStatus(
  createdAt: string,
  now: number = Date.now()
): OrderStatus {
  const created = new Date(createdAt).getTime()
  if (Number.isNaN(created)) return 'Em preparo'

  const steps = Math.floor(Math.max(now - created, 0) / AUTO_ADVANCE_STEP_MS)
  const index = Math.min(steps, ORDER_STATUS_FLOW.length - 1)

  return ORDER_STATUS_FLOW[index]
}


export interface OrderItem {
  id: string
  name: string
  price: number
  quantity: number
}

export interface Order {
  id: string
  restaurantNames: string[]
  items: OrderItem[]
  itemCount: number
  subtotal: number
  deliveryFee: number
  total: number
  address?: string
  status: OrderStatus
  createdAt: string
}

export interface NewOrderInput {
  restaurantNames: string[]
  items: OrderItem[]
  subtotal: number
  deliveryFee: number
  total: number
  address: string
}

const seedOrders: Order[] = [
  {
    id: 'o1',
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    itemCount: 1,
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    address: 'R. das Flores, 123 — Osasco, SP',
    status: 'Entregue',
    createdAt: '2026-10-28T19:30:00',
  },
  {
    id: 'o2',
    restaurantNames: ['Verde Vivo — Saudável'],
    items: [{ id: 'r2-m1', name: 'Bowl Proteico', price: 32.5, quantity: 1 }],
    itemCount: 1,
    subtotal: 32.5,
    deliveryFee: 0,
    total: 32.5,
    address: 'R. das Flores, 123 — Osasco, SP',
    status: 'Entregue',
    createdAt: '2026-10-20T12:15:00',
  },
]

interface OrdersState {
  orders: Order[]
  addOrder: (input: NewOrderInput) => Order
  advanceOrderStatus: (orderId: string) => Order | undefined
  syncOrderStatuses: (now?: number) => number
}

export const useOrdersStore = create<OrdersState>()(
  persist(
    (set, get) => ({
      orders: [...seedOrders],

      addOrder: (input) => {
        const order: Order = {
          id: `o${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          restaurantNames: input.restaurantNames,
          items: input.items,
          itemCount: input.items.reduce((sum, item) => sum + item.quantity, 0),
          subtotal: input.subtotal,
          deliveryFee: input.deliveryFee,
          total: input.total,
          address: input.address,
          status: 'Em preparo',
          createdAt: new Date().toISOString(),
        }

        set({ orders: [order, ...get().orders] })
        return order
      },

      advanceOrderStatus: (orderId) => {
        const current = get().orders.find((order) => order.id === orderId)
        if (!current) return undefined

        const nextStatus = nextOrderStatus(current.status)
        if (!nextStatus) return current

        const updated: Order = { ...current, status: nextStatus }
        set({
          orders: get().orders.map((order) =>
            order.id === orderId ? updated : order
          ),
        })
        return updated
      },

      syncOrderStatuses: (now = Date.now()) => {
        let advancedCount = 0

        const orders = get().orders.map((order) => {
          const derived = deriveOrderStatus(order.createdAt, now)
          const currentIndex = ORDER_STATUS_FLOW.indexOf(order.status)
          const derivedIndex = ORDER_STATUS_FLOW.indexOf(derived)

          if (derivedIndex <= currentIndex) return order

          advancedCount += 1
          return { ...order, status: derived }
        })

        if (advancedCount > 0) set({ orders })

        return advancedCount
      },
    }),
    {
      name: 'foodflow-orders',
      partialize: (state) => ({ orders: state.orders }),
    }
  )
)
