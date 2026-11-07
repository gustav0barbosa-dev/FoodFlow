import type { ReactNode } from 'react'

/**
 * Em desktop, renderiza o app dentro de uma "moldura de celular".
 * Em mobile, ocupa a tela toda.
 */
export function MobileFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-0 sm:p-6">
      <div
        className="relative w-full max-w-[430px] h-screen sm:h-[844px] sm:rounded-[2.5rem] sm:shadow-2xl overflow-hidden bg-surface"
      >
        {children}
      </div>
    </div>
  )
}