import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ErrorState } from '@/components/common/ErrorState'

describe('ErrorState', () => {
  it('expõe um alerta e executa a ação de tentar novamente', () => {
    const onAction = vi.fn()

    render(<ErrorState description="Falha na conexão" onAction={onAction} />)

    expect(screen.getByRole('alert')).toBeTruthy()
    expect(screen.getByText('Falha na conexão')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('não renderiza botão quando não há ação', () => {
    render(<ErrorState description="Sem ação disponível" />)

    expect(screen.queryByRole('button')).toBeNull()
  })
})
