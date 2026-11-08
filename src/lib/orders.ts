import type { Order, OrderItem } from '@/store/ordersStore'
import { restaurants } from '@/data/mockData'

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatOrderDate(value: string) {
  return dateFormatter.format(new Date(value))
}

export function orderRestaurantLabel(order: Order) {
  const [first, ...rest] = order.restaurantNames
  if (!first) return 'Pedido'
  if (rest.length === 0) return first
  return `${first} + ${rest.length} ${rest.length === 1 ? 'restaurante' : 'restaurantes'}`
}

export interface OrderGroup {
  restaurantId: string
  restaurantName: string
  items: OrderItem[]
}

export function groupOrderItems(order: Order): OrderGroup[] {
  const groups: OrderGroup[] = []

  for (const item of order.items) {
    const restaurant = restaurants.find((r) =>
      r.menu.some((menuItem) => menuItem.id === item.id)
    )
    const restaurantId = restaurant?.id ?? 'unknown'
    const restaurantName = restaurant?.name ?? 'Restaurante'

    const existing = groups.find((group) => group.restaurantId === restaurantId)
    if (existing) {
      existing.items.push(item)
      continue
    }

    groups.push({ restaurantId, restaurantName, items: [item] })
  }

  return groups
}
