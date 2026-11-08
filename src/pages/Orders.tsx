import { ShoppingBag } from 'lucide-react'
import { useOrdersStore, type Order, type OrderStatus } from '@/store/ordersStore'
import { cn, formatBRL } from '@/lib/utils'

const statusStyles: Record<OrderStatus, string> = {
  'Em preparo': 'bg-amber-100 text-amber-700',
  'Saiu para entrega': 'bg-blue-100 text-blue-700',
  Entregue: 'bg-green-100 text-green-700',
}

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function restaurantLabel(order: Order) {
  const [first, ...rest] = order.restaurantNames
  if (!first) return 'Pedido'
  if (rest.length === 0) return first
  return `${first} + ${rest.length} ${rest.length === 1 ? 'restaurante' : 'restaurantes'}`
}

export function Orders() {
  const orders = useOrdersStore((s) => s.orders)

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
        <div className="flex flex-col items-center justify-center px-8 pt-24 text-center">
          <div className="w-20 h-20 rounded-full bg-white text-ink-soft flex items-center justify-center shadow-sm">
            <ShoppingBag size={32} />
          </div>
          <h2 className="mt-4 font-display text-lg font-bold text-ink">
            Você ainda não fez pedidos
          </h2>
          <p className="mt-1 text-sm text-ink-soft">
            Seus pedidos aparecerão aqui depois da primeira compra.
          </p>
        </div>
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
                    {restaurantLabel(order)}
                  </h2>
                  <p className="text-xs text-ink-soft mt-0.5">
                    {dateFormatter.format(new Date(order.createdAt))}
                  </p>
                </div>
                <span
                  className={cn(
                    'text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap',
                    statusStyles[order.status]
                  )}
                >
                  {order.status}
                </span>
              </div>

              <p className="mt-2 text-xs text-ink-soft line-clamp-2">
                {order.items.map((item) => `${item.quantity}x ${item.name}`).join(' · ')}
              </p>

              <div className="mt-3 flex items-center justify-between">
                <span className="text-xs text-ink-soft">
                  {order.itemCount} {order.itemCount === 1 ? 'item' : 'itens'}
                </span>
                <span className="font-semibold text-primary">
                  {formatBRL(order.total)}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
