import { Link, useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, MapPin, ShoppingBag } from 'lucide-react'
import { toast } from 'sonner'
import {
  AUTO_ADVANCE_STEP_MS,
  ORDER_STATUS_FLOW,
  nextOrderStatus,
  useOrdersStore,
} from '@/store/ordersStore'
import { useEventsStore } from '@/store/eventsStore'
import { useOrderReorder } from '@/hooks/useOrderReorder'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { EmptyState } from '@/components/common/EmptyState'
import { formatOrderDate, groupOrderItems, orderRestaurantLabel } from '@/lib/orders'
import { cn, formatBRL } from '@/lib/utils'

export function OrderDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const order = useOrdersStore((s) => s.orders.find((item) => item.id === id))
  const advanceOrderStatus = useOrdersStore((s) => s.advanceOrderStatus)
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const reorder = useOrderReorder()

  if (!order) {
    return (
      <EmptyState
        icon={ShoppingBag}
        headingLevel="h1"
        title="Pedido não encontrado"
        description="Este pedido pode ter sido removido do histórico."
        actionLabel="Voltar aos pedidos"
        onAction={() => navigate('/pedidos')}
        className="h-full bg-surface-muted"
      />
    )
  }

  const groups = groupOrderItems(order)
  const activeStep = ORDER_STATUS_FLOW.indexOf(order.status)
  const nextStatus = nextOrderStatus(order.status)

  const handleAdvance = () => {
    const updated = advanceOrderStatus(order.id)
    if (!updated || updated.status === order.status) return

    trackEvent('order_status_updated', {
      orderId: updated.id,
      status: updated.status,
      previousStatus: order.status,
    })
    toast.success(`Status atualizado para "${updated.status}"`)
  }

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

      <div className="p-4 space-y-3 sm:max-w-[700px] sm:mx-auto">
        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <div className="flex items-start justify-between gap-2">
            <h2 className="font-semibold text-ink">{orderRestaurantLabel(order)}</h2>
            <div aria-live="polite">
              <OrderStatusBadge status={order.status} />
            </div>
          </div>

          <ol className="mt-4 space-y-3" aria-label="Acompanhamento do pedido">
            {ORDER_STATUS_FLOW.map((step, index) => {
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

          {nextStatus ? (
            <>
              <button
                type="button"
                onClick={handleAdvance}
                className="mt-4 w-full rounded-xl border border-primary/30 py-2.5 text-sm font-semibold text-primary hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              >
                {nextStatus === 'Saiu para entrega'
                  ? 'Confirmar saída para entrega'
                  : 'Confirmar entrega'}
              </button>
              <p className="mt-2 text-[11px] text-ink-soft text-center">
                O status também avança automaticamente a cada{' '}
                {AUTO_ADVANCE_STEP_MS / 60_000} min.
              </p>
            </>
          ) : (
            <p className="mt-4 text-xs text-ink-soft">
              Pedido concluído. Obrigado por pedir com a FoodFlow!
            </p>
          )}
        </section>

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-display font-semibold text-ink flex items-center gap-1.5 mb-2">
            <MapPin size={16} className="text-primary" />
            Endereço de entrega
          </h2>
          <p className="text-sm text-ink">
            {order.address ?? 'Endereço não informado'}
          </p>
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
