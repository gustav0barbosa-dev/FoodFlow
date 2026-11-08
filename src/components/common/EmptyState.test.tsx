import { Heart } from 'lucide-react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { EmptyState } from '@/components/common/EmptyState'

describe('EmptyState', () => {
  it('renderiza título, descrição e ação', () => {
    const onAction = vi.fn()

    render(
      <EmptyState
        icon={Heart}
        title="Nada por aqui"
        description="Adicione itens para começar."
        actionLabel="Explorar"
        onAction={onAction}
      />
    )

    expect(screen.getByRole('heading', { name: 'Nada por aqui' })).toBeTruthy()
    expect(screen.getByText('Adicione itens para começar.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Explorar' }))
    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('usa h1 quando solicitado e omite a ação sem handler', () => {
    render(
      <EmptyState icon={Heart} headingLevel="h1" title="Página vazia" />
    )

    expect(
      screen.getByRole('heading', { level: 1, name: 'Página vazia' })
    ).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
