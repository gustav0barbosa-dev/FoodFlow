import type { ReactNode } from 'react'

/**
 * Em desktop, renderiza o app dentro de uma "moldura de celular" com largura
 * limitada para não ocupar toda a tela. Em mobile, ocupa a tela toda.
 *
 * Breakpoints:
 * - < 640px: tela cheia (mobile)
 * - 640px - 1023px: moldura de ~640px, altura de 92vh
 * - >= 1024px: moldura de ~820px, altura de 92vh
 *
 * A altura precisa ser definida (h-[...]) também no desktop. Com `h-auto`,
 * os filhos `h-full` não têm referência e o scroll interno deixa de funcionar.
 */
export function MobileFrame({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-surface-muted sm:p-4">
      <div className="relative h-[100dvh] w-full max-w-[430px] overflow-hidden bg-surface sm:h-[92vh] sm:max-h-[92vh] sm:max-w-[640px] sm:rounded-[2.5rem] sm:shadow-2xl lg:max-w-[820px]">
        {children}
      </div>
    </div>
  )
}
