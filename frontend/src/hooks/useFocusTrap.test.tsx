import { useRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useFocusTrap } from '@/hooks/useFocusTrap'

function Harness({ open }: { open: boolean }) {
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(open, dialogRef)

  return (
    <div>
      <button type="button">Abrir</button>
      {open && (
        <div ref={dialogRef} role="dialog" aria-modal="true" tabIndex={-1}>
          <button type="button">Primeiro</button>
          <button type="button">Último</button>
        </div>
      )}
    </div>
  )
}

describe('useFocusTrap', () => {
  it('foca o primeiro controle ao abrir', () => {
    const { rerender } = render(<Harness open={false} />)
    screen.getByRole('button', { name: 'Abrir' }).focus()

    rerender(<Harness open />)

    expect(document.activeElement).toBe(
      screen.getByRole('button', { name: 'Primeiro' })
    )
  })

  it('mantém o Tab dentro do diálogo', () => {
    render(<Harness open />)

    const first = screen.getByRole('button', { name: 'Primeiro' })
    const last = screen.getByRole('button', { name: 'Último' })

    last.focus()
    fireEvent.keyDown(document, { key: 'Tab' })
    expect(document.activeElement).toBe(first)

    first.focus()
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('traz o foco de volta para o abridor ao fechar', () => {
    const { rerender } = render(<Harness open={false} />)
    const opener = screen.getByRole('button', { name: 'Abrir' })
    opener.focus()

    rerender(<Harness open />)
    expect(screen.getByRole('dialog')).toBeTruthy()

    rerender(<Harness open={false} />)
    expect(document.activeElement).toBe(opener)
  })
})
