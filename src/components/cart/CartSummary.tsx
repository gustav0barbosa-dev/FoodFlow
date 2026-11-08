import { formatBRL } from '@/lib/utils'

export function CartSummary({
  subtotal,
  deliveryFee,
  total,
}: {
  subtotal: number
  deliveryFee: number
  total: number
}) {
  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <h2 className="font-display font-semibold text-ink mb-2">Resumo do pedido</h2>
      <dl className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-ink-soft">Subtotal</dt>
          <dd className="text-ink">{formatBRL(subtotal)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-ink-soft">Entrega</dt>
          <dd className="text-ink">
            {deliveryFee === 0 ? 'Grátis' : formatBRL(deliveryFee)}
          </dd>
        </div>
        <div className="flex items-center justify-between border-t border-gray-100 pt-2">
          <dt className="font-semibold text-ink">Total</dt>
          <dd className="font-bold text-primary">{formatBRL(total)}</dd>
        </div>
      </dl>
    </section>
  )
}
