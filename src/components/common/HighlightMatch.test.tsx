import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HighlightMatch } from '@/components/common/HighlightMatch'

describe('HighlightMatch', () => {
  it('destaca a correspondência ignorando acentos', () => {
    render(<HighlightMatch text="Açaí Bowl" query="acai" />)

    expect(screen.getByText('Açaí').tagName).toBe('MARK')
    expect(screen.getByText(/Bowl/)).toBeTruthy()
  })

  it('não destaca nada quando a busca está vazia', () => {
    const { container } = render(<HighlightMatch text="Açaí Bowl" query="" />)

    expect(container.querySelector('mark')).toBeNull()
    expect(container.textContent).toBe('Açaí Bowl')
  })
})
