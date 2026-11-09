import { Receipt, UtensilsCrossed, Wallet } from 'lucide-react'
import { useOrdersStore } from '@/store/ordersStore'
import { getOrderMetrics } from '@/lib/metrics'
import { formatBRL } from '@/lib/utils'

export function ProfileStats() {
  const orders = useOrdersStore((s) => s.orders)
  const { orderCount, totalSpent, favoriteRestaurant } = getOrderMetrics(orders)

  return (
    <section
      aria-labelledby="profile-stats-title"
      className="bg-white rounded-2xl p-4 border border-gray-100"
    >
      <h2 id="profile-stats-title" className="font-semibold text-ink mb-3">
        Seu resumo
      </h2>

      <dl className="grid grid-cols-2 gap-2">
        <div className="bg-surface-muted rounded-xl px-3 py-3">
          <dt className="flex items-center gap-1 text-[11px] text-ink-soft">
            <Receipt size={12} aria-hidden="true" />
            Pedidos
          </dt>
          <dd className="mt-1 font-display text-lg font-bold text-ink">{orderCount}</dd>
        </div>

        <div className="bg-surface-muted rounded-xl px-3 py-3">
          <dt className="flex items-center gap-1 text-[11px] text-ink-soft">
            <Wallet size={12} aria-hidden="true" />
            Gasto total
          </dt>
          <dd className="mt-1 font-display text-lg font-bold text-primary">
            {formatBRL(totalSpent)}
          </dd>
        </div>

        <div className="col-span-2 bg-surface-muted rounded-xl px-3 py-3">
          <dt className="flex items-center gap-1 text-[11px] text-ink-soft">
            <UtensilsCrossed size={12} aria-hidden="true" />
            Restaurante favorito
          </dt>
          <dd
            className="mt-1 text-sm font-semibold text-ink truncate"
            title={favoriteRestaurant ?? undefined}
          >
            {favoriteRestaurant ?? 'Sem pedidos ainda'}
          </dd>
        </div>
      </dl>
    </section>
  )
}
