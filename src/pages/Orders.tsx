import { ShoppingBag } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { restaurants } from '@/data/mockData'
import { useOrdersStore, type Order, type OrderStatus } from '@/store/ordersStore'
import { useCartStore } from '@/store/cartStore'
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
  const addItem = useCartStore((s) => s.addItem)
  const navigate = useNavigate()

  const handleReorder = (order: Order) => {
    let addedCount = 0

    for (const line of order.items) {
      const restaurant = restaurants.find((r) =>
        r.menu.some((menuItem) => menuItem.id === line.id)
      )
      const menuItem = restaurant?.menu.find((item) => item.id === line.id)
      if (!restaurant || !menuItem) continue

      for (let i = 0; i < line.quantity; i += 1) {
        addItem(restaurant.id, restaurant.name, menuItem)
      }
      addedCount += line.quantity
    }

    if (addedCount === 0) {
      toast.error('Não foi possível repetir este pedido')
      return
    }

    toast.success(
      addedCount === 1
        ? '1 item adicionado à sacola'
        : `${addedCount} itens adicionados à sacola`
    )
    navigate('/sacola')
  }

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

              <div className="mt-3 flex items-end justify-between gap-2">
                <div>
                  <span className="block text-xs text-ink-soft">
                    {order.itemCount} {order.itemCount === 1 ? 'item' : 'itens'}
                  </span>
                  <span className="font-semibold text-primary">
                    {formatBRL(order.total)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleReorder(order)}
                  aria-label={`Pedir novamente: ${restaurantLabel(order)}`}
                  className="text-sm font-medium text-primary px-3 py-1.5 rounded-full border border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Pedir novamente
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
