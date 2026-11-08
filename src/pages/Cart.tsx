import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, ShoppingBag } from 'lucide-react'
import type { CartLine } from '@/types'
import { restaurants } from '@/data/mockData'
import { useCartStore } from '@/store/cartStore'
import { useOrdersStore } from '@/store/ordersStore'
import { useAddressStore } from '@/store/addressStore'
import { useEventsStore } from '@/store/eventsStore'
import { formatBRL } from '@/lib/utils'
import { CartLineItem } from '@/components/cart/CartLineItem'
import { CartSummary } from '@/components/cart/CartSummary'
import { DeliveryAddress } from '@/components/cart/DeliveryAddress'
import { ConfirmOrderModal } from '@/components/cart/ConfirmOrderModal'

interface CartGroup {
  restaurantId: string
  restaurantName: string
  deliveryFee: number
  lines: CartLine[]
}

function groupByRestaurant(lines: CartLine[]): CartGroup[] {
  const groups: CartGroup[] = []

  for (const line of lines) {
    const existing = groups.find((group) => group.restaurantId === line.restaurantId)
    if (existing) {
      existing.lines.push(line)
      continue
    }

    const restaurant = restaurants.find((r) => r.id === line.restaurantId)
    groups.push({
      restaurantId: line.restaurantId,
      restaurantName: line.restaurantName,
      deliveryFee: restaurant?.deliveryFee ?? 0,
      lines: [line],
    })
  }

  return groups
}

export function Cart() {
  const navigate = useNavigate()
  const lines = useCartStore((s) => s.lines)
  const clear = useCartStore((s) => s.clear)
  const addOrder = useOrdersStore((s) => s.addOrder)
  const address = useAddressStore((s) => s.address)
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const groups = groupByRestaurant(lines)
  const itemCount = lines.reduce((sum, line) => sum + line.quantity, 0)
  const subtotal = lines.reduce((sum, line) => sum + line.item.price * line.quantity, 0)
  const deliveryFee = groups.reduce((sum, group) => sum + group.deliveryFee, 0)
  const total = subtotal + deliveryFee

  const handleCloseModal = () => setConfirmOpen(false)

  const handleViewOrders = () => {
    setConfirmOpen(false)
    navigate('/pedidos')
  }

  const handleGoHome = () => {
    setConfirmOpen(false)
    navigate('/home')
  }

  const handleConfirm = () => {
    const order = addOrder({
      restaurantNames: groups.map((group) => group.restaurantName),
      items: lines.map((line) => ({
        id: line.item.id,
        name: line.item.name,
        price: line.item.price,
        quantity: line.quantity,
      })),
      subtotal,
      deliveryFee,
      total,
      address,
    })
    trackEvent('order_completed', {
      orderId: order.id,
      itemCount: order.itemCount,
      total: order.total,
      restaurantIds: groups.map((group) => group.restaurantId),
    })
    clear()
  }

  return (
    <div className="h-full flex flex-col bg-surface-muted relative">
      <header className="shrink-0 bg-white px-4 py-4 border-b border-gray-100 flex items-center gap-2">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-full flex items-center justify-center text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="Voltar"
        >
          <ChevronLeft size={20} />
        </button>
        <div>
          <h1 className="font-display font-bold text-lg text-ink leading-tight">Sacola</h1>
          <p className="text-xs text-ink-soft">
            {itemCount === 0
              ? 'Nenhum item'
              : `${itemCount} ${itemCount === 1 ? 'item' : 'itens'}`}
          </p>
        </div>
      </header>

      {lines.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center px-8 text-center">
          <div className="w-20 h-20 rounded-full bg-white text-ink-soft flex items-center justify-center shadow-sm">
            <ShoppingBag size={32} />
          </div>
          <h2 className="mt-4 font-display text-lg font-bold text-ink">
            Sua sacola está vazia
          </h2>
          <p className="mt-1 text-sm text-ink-soft">
            Adicione itens de um restaurante para começar seu pedido.
          </p>
          <button
            type="button"
            onClick={() => navigate('/home')}
            className="mt-6 bg-primary text-white rounded-2xl px-6 py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            Explorar restaurantes
          </button>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {groups.map((group) => (
              <section
                key={group.restaurantId}
                className="bg-white rounded-2xl p-4 border border-gray-100"
              >
                <header className="flex items-center justify-between gap-3 border-b border-gray-100 pb-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/restaurante/${group.restaurantId}`)}
                    aria-label={`Abrir ${group.restaurantName}`}
                    className="text-sm font-semibold text-ink hover:text-primary rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    {group.restaurantName}
                  </button>
                  <span className="text-xs text-ink-soft shrink-0">
                    {group.deliveryFee === 0
                      ? 'Frete grátis'
                      : `Entrega ${formatBRL(group.deliveryFee)}`}
                  </span>
                </header>

                <div className="divide-y divide-gray-100">
                  {group.lines.map((line) => (
                    <CartLineItem key={line.item.id} line={line} />
                  ))}
                </div>
              </section>
            ))}

            <DeliveryAddress />
            <CartSummary
              subtotal={subtotal}
              deliveryFee={deliveryFee}
              total={total}
            />
          </div>

          <div className="shrink-0 bg-white border-t border-gray-100 p-4">
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              className="w-full bg-primary text-white rounded-2xl py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              Finalizar pedido · {formatBRL(total)}
            </button>
          </div>
        </>
      )}

      <ConfirmOrderModal
        open={confirmOpen}
        onClose={handleCloseModal}
        itemCount={itemCount}
        subtotal={subtotal}
        deliveryFee={deliveryFee}
        total={total}
        onConfirm={handleConfirm}
        onViewOrders={handleViewOrders}
        onGoHome={handleGoHome}
      />
    </div>
  )
}
