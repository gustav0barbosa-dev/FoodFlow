import { ShoppingBag } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useOrdersStore } from '@/store/ordersStore'
import type { Order, OrderStatus } from '@/store/ordersStore'
import { useOrderStatusFilterStore, type OrderStatusFilter } from '@/store/orderStatusFilterStore'
import { useOrderReorder } from '@/hooks/useOrderReorder'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { formatOrderDate, orderRestaurantLabel } from '@/lib/orders'
import { formatBRL } from '@/lib/utils'

export type { OrderStatusFilter } from '@/store/orderStatusFilterStore'

const STATUS_FILTER_OPTIONS: {
  value: OrderStatusFilter
  label: string
}[] = [
  { value: 'todos', label: 'Todos' },
  { value: 'andamento', label: 'Em andamento' },
  { value: 'entregues', label: 'Entregues' },
]

const IN_PROGRESS_STATUSES: OrderStatus[] = ['Em preparo', 'Saiu para entrega']

function matchesStatusFilter(order: Order, filter: OrderStatusFilter): boolean {
  if (filter === 'todos') return true
  if (filter === 'entregues') return order.status === 'Entregue'
  return IN_PROGRESS_STATUSES.includes(order.status)
}

export function Orders() {
  const navigate = useNavigate()
  const orders = useOrdersStore((s) => s.orders)
  const statusFilter = useOrderStatusFilterStore((s) => s.filter)
  const setStatusFilter = useOrderStatusFilterStore((s) => s.setFilter)
  const reorder = useOrderReorder()

  const filteredOrders = orders.filter((o) => matchesStatusFilter(o, statusFilter))

  return (
    <div className="h-full overflow-y-auto pb-6 bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 py-4 border-b border-gray-100">
        <h1 className="font-display font-bold text-lg text-ink">Pedidos</h1>
        <p className="text-xs text-ink-soft mt-0.5">
          {filteredOrders.length === 0
            ? 'Nenhum pedido ainda'
            : `${filteredOrders.length} ${filteredOrders.length === 1 ? 'pedido' : 'pedidos'}`}
        </p>
      </header>

      <div className="px-4 mt-4 mb-2 sm:max-w-[700px] sm:mx-auto">
        <label htmlFor="pedidos-status-filtro" className="text-xs text-ink-soft block mb-1">
          Filtrar por status
        </label>
        <select
          id="pedidos-status-filtro"
          value={statusFilter}
          onChange={(event) =>
            setStatusFilter(event.target.value as OrderStatusFilter)
          }
          className="w-full max-w-xs rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {STATUS_FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {filteredOrders.length === 0 ? (
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
          {filteredOrders.map((order) => (
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
