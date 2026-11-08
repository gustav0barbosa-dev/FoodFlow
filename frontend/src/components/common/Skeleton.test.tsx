import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Skeleton } from '@/components/common/Skeleton'

describe('Skeleton', () => {
  it('renderiza a variante de card com imagem e linhas', () => {
    const { container } = render(<Skeleton variant="card" />)
    const root = container.firstElementChild

    expect(root?.className).toContain('animate-pulse')
    expect(root?.querySelector('.h-32')).toBeTruthy()
    expect(root?.querySelector('.w-20')).toBeNull()
  })

  it('renderiza a variante de linha com miniatura lateral', () => {
    const { container } = render(<Skeleton variant="row" />)
    const root = container.firstElementChild

    expect(root?.className).toContain('animate-pulse')
    expect(root?.querySelector('.w-20')).toBeTruthy()
    expect(root?.querySelector('.h-32')).toBeNull()
  })

  it('é decorativo para leitores de tela', () => {
    const { container } = render(<Skeleton />)

    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})
