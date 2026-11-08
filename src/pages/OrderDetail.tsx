import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, ShoppingBag } from 'lucide-react'
import { useOrdersStore, type OrderStatus } from '@/store/ordersStore'
import { useOrderReorder } from '@/hooks/useOrderReorder'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { formatOrderDate, groupOrderItems, orderRestaurantLabel } from '@/lib/orders'
import { cn, formatBRL } from '@/lib/utils'

const STATUS_STEPS: OrderStatus[] = ['Em preparo', 'Saiu para entrega', 'Entregue']

export function OrderDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const order = useOrdersStore((s) => s.orders.find((item) => item.id === id))
  const reorder = useOrderReorder()

  if (!order) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-8 text-center bg-surface-muted">
        <div className="w-20 h-20 rounded-full bg-white text-ink-soft flex items-center justify-center shadow-sm">
          <ShoppingBag size={32} />
        </div>
        <h1 className="mt-4 font-display text-lg font-bold text-ink">
          Pedido não encontrado
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Este pedido pode ter sido removido do histórico.
        </p>
        <button
          type="button"
          onClick={() => navigate('/pedidos')}
          className="mt-6 bg-primary text-white rounded-2xl px-6 py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Voltar aos pedidos
        </button>
      </div>
    )
  }

  const groups = groupOrderItems(order)
  const activeStep = STATUS_STEPS.indexOf(order.status)

  return (
    <div className="h-full overflow-y-auto bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 py-4 border-b border-gray-100 flex items-center gap-2">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-full flex items-center justify-center text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="Voltar"
        >
          <ChevronLeft size={20} />
        </button>
        <div>
          <h1 className="font-display font-bold text-lg text-ink leading-tight">
            Detalhes do pedido
          </h1>
          <p className="text-xs text-ink-soft">{formatOrderDate(order.createdAt)}</p>
        </div>
      </header>

      <div className="p-4 space-y-3">
        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <div className="flex items-start justify-between gap-2">
            <h2 className="font-semibold text-ink">{orderRestaurantLabel(order)}</h2>
            <OrderStatusBadge status={order.status} />
          </div>

          <ol className="mt-4 space-y-3" aria-label="Acompanhamento do pedido">
            {STATUS_STEPS.map((step, index) => {
              const reached = index <= activeStep
              return (
                <li
                  key={step}
                  aria-current={step === order.status ? 'step' : undefined}
                  className="flex items-center gap-2"
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      'w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0',
                      reached ? 'bg-primary text-white' : 'bg-surface-muted text-ink-soft'
                    )}
                  >
                    {index + 1}
                  </span>
                  <span
                    className={cn(
                      'text-sm',
                      reached ? 'text-ink font-medium' : 'text-ink-soft'
                    )}
                  >
                    {step}
                  </span>
                </li>
              )
            })}
          </ol>
        </section>

        {groups.map((group) => (
          <section
            key={group.restaurantId}
            className="bg-white rounded-2xl p-4 border border-gray-100"
          >
            <div className="flex items-center justify-between gap-2 border-b border-gray-100 pb-2">
              <h2 className="text-sm font-semibold text-ink truncate">
                {group.restaurantName}
              </h2>
              {group.restaurantId !== 'unknown' && (
                <Link
                  to={`/restaurante/${group.restaurantId}`}
                  className="text-xs font-medium text-primary rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  Abrir restaurante
                </Link>
              )}
            </div>

            <ul className="divide-y divide-gray-100">
              {group.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2 py-2">
                  <span className="text-sm text-ink">
                    <span className="text-ink-soft">{item.quantity}x</span> {item.name}
                  </span>
                  <span className="text-sm text-ink shrink-0">
                    {formatBRL(item.price * item.quantity)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-display font-semibold text-ink mb-2">Resumo do pedido</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-ink-soft">Subtotal</dt>
              <dd className="text-ink">{formatBRL(order.subtotal)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-ink-soft">Entrega</dt>
              <dd className="text-ink">
                {order.deliveryFee === 0 ? 'Grátis' : formatBRL(order.deliveryFee)}
              </dd>
            </div>
            <div className="flex items-center justify-between border-t border-gray-100 pt-2">
              <dt className="font-semibold text-ink">Total</dt>
              <dd className="font-bold text-primary">{formatBRL(order.total)}</dd>
            </div>
          </dl>
        </section>

        <button
          type="button"
          onClick={() => reorder(order)}
          className="w-full bg-primary text-white rounded-2xl py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Pedir novamente · {formatBRL(order.total)}
        </button>
        <Link
          to="/pedidos"
          className="block text-center text-sm font-medium text-ink-soft py-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Voltar aos pedidos
        </Link>
      </div>
    </div>
  )
}
