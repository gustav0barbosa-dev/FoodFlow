import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AUTO_ADVANCE_STEP_MS,
  useOrdersStore,
  type NewOrderInput,
} from '@/store/ordersStore'
import { useOrderAutoAdvance } from '@/hooks/useOrderAutoAdvance'

const NOW = new Date('2026-11-08T12:00:00.000Z')

function buildOrder(): NewOrderInput {
  return {
    restaurantNames: ['Sabor da Vila'],
    items: [{ id: 'r1-m1', name: 'Feijoada Completa', price: 42.9, quantity: 1 }],
    subtotal: 42.9,
    deliveryFee: 5.99,
    total: 48.89,
    address: 'R. das Flores, 123 — Osasco, SP',
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useOrderAutoAdvance', () => {
  it('sincroniza no mount e avança quando o tempo de preparo termina', () => {
    useOrdersStore.getState().addOrder(buildOrder())

    const { unmount } = renderHook(() => useOrderAutoAdvance())

    expect(useOrdersStore.getState().orders[0].status).toBe('Em preparo')

    act(() => {
      vi.advanceTimersByTime(AUTO_ADVANCE_STEP_MS)
    })

    expect(useOrdersStore.getState().orders[0].status).toBe('Saiu para entrega')

    act(() => {
      vi.advanceTimersByTime(AUTO_ADVANCE_STEP_MS)
    })

    expect(useOrdersStore.getState().orders[0].status).toBe('Entregue')

    unmount()
  })

  it('recupera o atraso ao montar com um pedido antigo', () => {
    useOrdersStore.getState().addOrder(buildOrder())

    act(() => {
      vi.advanceTimersByTime(AUTO_ADVANCE_STEP_MS * 3)
    })

    const { unmount } = renderHook(() => useOrderAutoAdvance())

    expect(useOrdersStore.getState().orders[0].status).toBe('Entregue')

    unmount()
  })
})
