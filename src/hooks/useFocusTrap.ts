import { useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
  ).filter(
    (element) =>
      element.tabIndex >= 0 && element.getAttribute('aria-hidden') !== 'true'
  )
}

/**
 * Keeps keyboard focus inside the container while it is open,
 * moves focus to the first control on open (and when `focusKey` changes),
 * and returns focus to the opener on close.
 */
export function useFocusTrap(
  open: boolean,
  containerRef: RefObject<HTMLElement>,
  focusKey?: string
) {
  const openerRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return

    const container = containerRef.current
    if (!container) return

    openerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return

      const node = containerRef.current
      if (!node) return

      const focusable = getFocusableElements(node)
      if (focusable.length === 0) {
        event.preventDefault()
        node.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement

      if (!(active instanceof HTMLElement) || !node.contains(active)) {
        event.preventDefault()
        first.focus()
        return
      }

      if (event.shiftKey && (active === first || active === node)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && (active === last || active === node)) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      openerRef.current?.focus()
      openerRef.current = null
    }
  }, [open, containerRef])

  useEffect(() => {
    if (!open) return

    const container = containerRef.current
    if (!container) return

    const [first] = getFocusableElements(container)
    ;(first ?? container).focus()
  }, [open, containerRef, focusKey])
}
