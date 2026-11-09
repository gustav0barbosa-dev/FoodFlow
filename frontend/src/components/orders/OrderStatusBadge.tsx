import type { OrderStatus } from '@/store/ordersStore'
import { cn } from '@/lib/utils'

const statusStyles: Record<OrderStatus, string> = {
  'Em preparo': 'bg-amber-100 text-amber-700',
  'Saiu para entrega': 'bg-blue-100 text-blue-700',
  Entregue: 'bg-green-100 text-green-700',
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span
      className={cn(
        'text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap',
        statusStyles[status]
      )}
    >
      {status}
    </span>
  )
}
