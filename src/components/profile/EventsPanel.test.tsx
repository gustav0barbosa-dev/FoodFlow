import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EventsPanel } from '@/components/profile/EventsPanel'
import { useEventsStore, type AnalyticsEvent } from '@/store/eventsStore'

function seedEvents() {
  const now = new Date().toISOString()
  const events: AnalyticsEvent[] = [
    {
      id: 'e1',
      type: 'search_performed',
      payload: { query: 'pizza' },
      createdAt: now,
    },
    {
      id: 'e2',
      type: 'add_to_cart',
      payload: { itemId: 'r1-m1' },
      createdAt: now,
    },
  ]
  useEventsStore.setState({ events })
}

describe('EventsPanel', () => {
  it('filtra os eventos pelo tipo selecionado', () => {
    seedEvents()
    render(<EventsPanel />)

    const list = screen.getByRole('list', { name: 'Eventos recentes' })
    expect(within(list).getByText('Busca realizada')).toBeTruthy()
    expect(within(list).getByText('Item adicionado')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Filtrar por tipo de evento'), {
      target: { value: 'add_to_cart' },
    })

    expect(within(list).queryByText('Busca realizada')).toBeNull()
    expect(within(list).getByText('Item adicionado')).toBeTruthy()
  })

  it('mostra contadores agregados por tipo do período', () => {
    seedEvents()
    render(<EventsPanel />)

    const summary = screen.getByRole('list', { name: 'Contagem por tipo' })
    expect(within(summary).getByText('Busca realizada · 1')).toBeTruthy()
    expect(within(summary).getByText('Item adicionado · 1')).toBeTruthy()
  })
})
