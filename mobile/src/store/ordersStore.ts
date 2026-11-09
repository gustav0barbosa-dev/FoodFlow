import { create } from 'zustand'

export interface Order {
  id: string
  restaurantNames: string[]
  items: {
    id: string
    name: string
    price: number
    quantity: number
  }[]
  itemCount: number
  subtotal: number
  deliveryFee: number
  total: number
  address?: string
  status: 'Em preparo' | 'Saiu para entrega' | 'Entregue'
  createdAt: string
}

export interface NewOrderInput {
  restaurantNames: string[]
  items: {
    id: string
    name: string
    price: number
    quantity: number
  }[]
  subtotal: number
  deliveryFee: number
  total: number
  address: string
}

interface OrdersState {
  orders: Order[]
  addOrder: (input: NewOrderInput) => Order
}

export const useOrdersStore = create<OrdersState>((set, get) => ({
  orders: [],

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
}))
