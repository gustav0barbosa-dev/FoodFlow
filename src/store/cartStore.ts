import { create } from 'zustand'
import type { CartLine, MenuItem } from '@/types'

interface CartState {
  lines: CartLine[]
  addItem: (restaurantId: string, restaurantName: string, item: MenuItem) => void
  removeItem: (itemId: string) => void
  clear: () => void
  total: () => number
  count: () => number
}

export const useCartStore = create<CartState>((set, get) => ({
  lines: [],

  addItem: (restaurantId, restaurantName, item) => {
    const existing = get().lines.find((l) => l.item.id === item.id)
    if (existing) {
      set({
        lines: get().lines.map((l) =>
          l.item.id === item.id ? { ...l, quantity: l.quantity + 1 } : l
        ),
      })
    } else {
      set({
        lines: [...get().lines, { restaurantId, restaurantName, item, quantity: 1 }],
      })
    }
  },

  removeItem: (itemId) =>
    set({ lines: get().lines.filter((l) => l.item.id !== itemId) }),

  clear: () => set({ lines: [] }),

  total: () =>
    get().lines.reduce((sum, l) => sum + l.item.price * l.quantity, 0),

  count: () => get().lines.reduce((sum, l) => sum + l.quantity, 0),
}))