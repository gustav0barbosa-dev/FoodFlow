import { describe, expect, it } from 'vitest'
import {
  DEFAULT_ORDER_STATUS_FILTER,
  useOrderStatusFilterStore,
} from '@/store/orderStatusFilterStore'

describe('orderStatusFilterStore', () => {
  it('inicia com o filtro padrão', () => {
    expect(useOrderStatusFilterStore.getState().filter).toBe(
      DEFAULT_ORDER_STATUS_FILTER
    )
  })

  it('persiste o filtro escolhido em localStorage', () => {
    useOrderStatusFilterStore.getState().setFilter('entregues')

    expect(localStorage.getItem('foodflow-order-status-filter')).toContain(
      'entregues'
    )
  })

  it('reidrata o filtro salvo', async () => {
    localStorage.setItem(
      'foodflow-order-status-filter',
      JSON.stringify({ state: { filter: 'andamento' }, version: 0 })
    )

    await useOrderStatusFilterStore.persist.rehydrate()

    expect(useOrderStatusFilterStore.getState().filter).toBe('andamento')
  })

  it('ignora um valor inválido vindo do localStorage', async () => {
    localStorage.setItem(
      'foodflow-order-status-filter',
      JSON.stringify({ state: { filter: 'invalido' }, version: 0 })
    )

    await useOrderStatusFilterStore.persist.rehydrate()

    expect(useOrderStatusFilterStore.getState().filter).toBe(
      DEFAULT_ORDER_STATUS_FILTER
    )
  })
})
