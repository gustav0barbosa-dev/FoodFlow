import { Minus, Plus, Trash2 } from 'lucide-react'
import type { CartLine } from '@/types'
import { useCartStore } from '@/store/cartStore'
import { formatBRL } from '@/lib/utils'

const controlClass =
  'w-7 h-7 rounded-full border border-gray-200 flex items-center justify-center text-ink transition-colors hover:bg-surface-muted disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

export function CartLineItem({ line }: { line: CartLine }) {
  const incrementItem = useCartStore((s) => s.incrementItem)
  const decrementItem = useCartStore((s) => s.decrementItem)
  const removeItem = useCartStore((s) => s.removeItem)
  const lineTotal = line.item.price * line.quantity

  return (
    <div className="flex gap-3 py-3">
      <img
        src={line.item.image}
        alt={line.item.name}
        className="w-16 h-16 rounded-xl object-cover shrink-0"
      />

      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-sm font-medium text-ink truncate">{line.item.name}</h3>
            <p className="text-xs text-ink-soft truncate">{line.restaurantName}</p>
            <p className="text-xs text-ink-soft mt-0.5">
              {formatBRL(line.item.price)} cada
            </p>
          </div>

          <button
            type="button"
            onClick={() => removeItem(line.item.id)}
            className="p-1.5 rounded-lg text-ink-soft hover:text-primary hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label={`Remover ${line.item.name} da sacola`}
          >
            <Trash2 size={16} />
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => decrementItem(line.item.id)}
              disabled={line.quantity <= 1}
              className={controlClass}
              aria-label={`Diminuir quantidade de ${line.item.name}`}
            >
              <Minus size={14} />
            </button>
            <span
              className="min-w-6 text-center text-sm font-medium text-ink"
              aria-live="polite"
            >
              {line.quantity}
            </span>
            <button
              type="button"
              onClick={() => incrementItem(line.item.id)}
              className={controlClass}
              aria-label={`Aumentar quantidade de ${line.item.name}`}
            >
              <Plus size={14} />
            </button>
          </div>

          <span className="text-sm font-semibold text-ink">{formatBRL(lineTotal)}</span>
        </div>
      </div>
    </div>
  )
}
