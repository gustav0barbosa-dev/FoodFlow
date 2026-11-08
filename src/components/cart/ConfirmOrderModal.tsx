import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, X } from 'lucide-react'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { formatBRL } from '@/lib/utils'

type Phase = 'confirm' | 'success'

interface ConfirmOrderModalProps {
  open: boolean
  onClose: () => void
  itemCount: number
  subtotal: number
  deliveryFee: number
  total: number
  onConfirm: () => void
  onViewOrders: () => void
  onGoHome: () => void
}

const primaryButtonClass =
  'w-full bg-primary text-white rounded-2xl py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2'

const secondaryButtonClass =
  'w-full rounded-2xl py-3 text-sm font-medium text-ink-soft hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

export function ConfirmOrderModal({
  open,
  onClose,
  itemCount,
  subtotal,
  deliveryFee,
  total,
  onConfirm,
  onViewOrders,
  onGoHome,
}: ConfirmOrderModalProps) {
  const [phase, setPhase] = useState<Phase>('confirm')
  const dialogRef = useRef<HTMLDivElement>(null)
  useFocusTrap(open, dialogRef, phase)

  useEffect(() => {
    if (!open) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  const handleConfirm = () => {
    onConfirm()
    setPhase('success')
  }

  return (
    <AnimatePresence onExitComplete={() => setPhase('confirm')}>
      {open && (
        <motion.div
          className="absolute inset-0 z-50 flex items-end justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            onClick={onClose}
            tabIndex={-1}
            aria-label="Fechar confirmação do pedido"
            className="absolute inset-0 bg-black/40"
          />

          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-order-title"
            tabIndex={-1}
            className="relative w-full max-h-full overflow-y-auto bg-white rounded-t-3xl p-5 pb-7 shadow-2xl focus:outline-none"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          >
            {phase === 'confirm' ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2
                    id="confirm-order-title"
                    className="font-display text-lg font-bold text-ink"
                  >
                    Confirmar pedido
                  </h2>
                  <button
                    type="button"
                    onClick={onClose}
                    className="p-1.5 rounded-lg text-ink-soft hover:text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label="Fechar"
                  >
                    <X size={18} />
                  </button>
                </div>

                <dl className="space-y-2 text-sm">
                  <div className="flex items-center justify-between">
                    <dt className="text-ink-soft">
                      Itens ({itemCount} {itemCount === 1 ? 'item' : 'itens'})
                    </dt>
                    <dd className="font-medium text-ink">{formatBRL(subtotal)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-ink-soft">Entrega</dt>
                    <dd className="font-medium text-ink">
                      {deliveryFee === 0 ? 'Grátis' : formatBRL(deliveryFee)}
                    </dd>
                  </div>
                  <div className="flex items-center justify-between border-t border-gray-100 pt-2">
                    <dt className="font-semibold text-ink">Total</dt>
                    <dd className="font-bold text-primary">{formatBRL(total)}</dd>
                  </div>
                </dl>

                <p className="mt-3 text-xs text-ink-soft">
                  O pagamento é feito na entrega. Nenhuma cobrança é feita agora.
                </p>

                <button type="button" onClick={handleConfirm} className={`mt-5 ${primaryButtonClass}`}>
                  Confirmar pedido
                </button>
                <button type="button" onClick={onClose} className={`mt-1 ${secondaryButtonClass}`}>
                  Continuar comprando
                </button>
              </>
            ) : (
              <div className="flex flex-col items-center text-center">
                <div className="w-16 h-16 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
                  <Check size={32} />
                </div>
                <h2
                  id="confirm-order-title"
                  className="mt-4 font-display text-xl font-bold text-ink"
                >
                  Pedido confirmado!
                </h2>
                <p className="mt-1 text-sm text-ink-soft">
                  Seu pedido foi enviado para o restaurante. Acompanhe o status em Pedidos.
                </p>

                <button type="button" onClick={onViewOrders} className={`mt-6 ${primaryButtonClass}`}>
                  Ver meus pedidos
                </button>
                <button type="button" onClick={onGoHome} className={`mt-1 ${secondaryButtonClass}`}>
                  Voltar ao início
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
