import type { ReactNode } from 'react'

/**
 * Em desktop, renderiza o app dentro de uma "moldura de celular" com largura
 * limitada para não ocupar toda a tela. Em mobile, ocupa a tela toda.
 *
 * Breakpoints:
 * - < 640px: tela cheia (mobile)
 * - 640px - 1023px: moldura de ~640px, altura máxima 92vh
 * - >= 1024px: moldura de ~820px, altura máxima 92vh
 */
export function MobileFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-0 bg-surface-muted">
      <div
        className="relative w-full max-w-[430px] sm:max-w-[640px] lg:max-w-[820px] h-screen sm:h-auto sm:max-h-[92vh] sm:rounded-[2.5rem] sm:shadow-2xl overflow-hidden bg-surface"
      >
        {children}
      </div>
    </div>
  )
}
