import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type OrderStatusFilter = 'todos' | 'andamento' | 'entregues'

export const DEFAULT_ORDER_STATUS_FILTER: OrderStatusFilter = 'todos'

interface OrderStatusFilterState {
  filter: OrderStatusFilter
  setFilter: (filter: OrderStatusFilter) => void
}

export const useOrderStatusFilterStore = create<OrderStatusFilterState>()(
  persist(
    (set) => ({
      filter: DEFAULT_ORDER_STATUS_FILTER,
      setFilter: (filter) => set({ filter }),
    }),
    {
      name: 'foodflow-order-status-filter',
      partialize: (state) => ({ filter: state.filter }),
      merge: (persisted, current) => {
        const stored = (persisted as { filter?: unknown } | undefined)?.filter

        return {
          ...current,
          filter:
            stored === 'todos' ||
            stored === 'andamento' ||
            stored === 'entregues'
              ? stored
              : current.filter,
        }
      },
    }
  )
)
