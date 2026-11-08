import { ShoppingBag } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useOrdersStore } from '@/store/ordersStore'
import { useOrderReorder } from '@/hooks/useOrderReorder'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { formatOrderDate, orderRestaurantLabel } from '@/lib/orders'
import { formatBRL } from '@/lib/utils'

export function Orders() {
  const navigate = useNavigate()
  const orders = useOrdersStore((s) => s.orders)
  const reorder = useOrderReorder()

  return (
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 py-4 border-b border-gray-100">
        <h1 className="font-display font-bold text-lg text-ink">Pedidos</h1>
        <p className="text-xs text-ink-soft mt-0.5">
          {orders.length === 0
            ? 'Nenhum pedido ainda'
            : `${orders.length} ${orders.length === 1 ? 'pedido' : 'pedidos'}`}
        </p>
      </header>

      {orders.length === 0 ? (
        <EmptyState
          icon={ShoppingBag}
          title="Você ainda não fez pedidos"
          description="Seus pedidos aparecerão aqui depois da primeira compra."
          actionLabel="Explorar restaurantes"
          onAction={() => navigate('/home')}
          className="pt-24"
        />
      ) : (
        <div className="p-4 space-y-3">
          {orders.map((order) => (
            <article
              key={order.id}
              className="bg-white rounded-2xl p-4 border border-gray-100"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="font-medium text-ink truncate">
                    {orderRestaurantLabel(order)}
                  </h2>
                  <p className="text-xs text-ink-soft mt-0.5">
                    {formatOrderDate(order.createdAt)}
                  </p>
                </div>
                <OrderStatusBadge status={order.status} />
              </div>

              <p className="mt-2 text-xs text-ink-soft line-clamp-2">
                {order.items.map((item) => `${item.quantity}x ${item.name}`).join(' · ')}
              </p>

              <div className="mt-3 flex items-end justify-between gap-2">
                <div>
                  <span className="block text-xs text-ink-soft">
                    {order.itemCount} {order.itemCount === 1 ? 'item' : 'itens'}
                  </span>
                  <span className="font-semibold text-primary">
                    {formatBRL(order.total)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    to={`/pedidos/${order.id}`}
                    aria-label={`Ver detalhes do pedido de ${orderRestaurantLabel(order)}`}
                    className="text-sm font-medium text-primary px-3 py-1.5 rounded-full hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    Detalhes
                  </Link>
                  <button
                    type="button"
                    onClick={() => reorder(order)}
                    aria-label={`Pedir novamente: ${orderRestaurantLabel(order)}`}
                    className="text-sm font-medium text-primary px-3 py-1.5 rounded-full border border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    Pedir novamente
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
