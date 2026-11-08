import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CartLine, MenuItem } from '@/types'

interface CartState {
  lines: CartLine[]
  addItem: (restaurantId: string, restaurantName: string, item: MenuItem) => void
  incrementItem: (itemId: string) => void
  decrementItem: (itemId: string) => void
  removeItem: (itemId: string) => void
  clear: () => void
  total: () => number
  count: () => number
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
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

      incrementItem: (itemId) =>
        set({
          lines: get().lines.map((l) =>
            l.item.id === itemId ? { ...l, quantity: l.quantity + 1 } : l
          ),
        }),

      decrementItem: (itemId) =>
        set({
          lines: get().lines.flatMap((l) => {
            if (l.item.id !== itemId) return [l]
            return l.quantity > 1 ? [{ ...l, quantity: l.quantity - 1 }] : []
          }),
        }),

      removeItem: (itemId) =>
        set({ lines: get().lines.filter((l) => l.item.id !== itemId) }),

      clear: () => set({ lines: [] }),

      // Subtotal of items only. Delivery fees are calculated by the cart page.
      total: () =>
        get().lines.reduce((sum, l) => sum + l.item.price * l.quantity, 0),

      count: () => get().lines.reduce((sum, l) => sum + l.quantity, 0),
    }),
    {
      name: 'foodflow-cart',
      partialize: (state) => ({ lines: state.lines }),
    }
  )
)
