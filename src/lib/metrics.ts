import type { Order } from '@/store/ordersStore'

export interface OrderMetrics {
  orderCount: number
  totalSpent: number
  favoriteRestaurant: string | null
}

export function getOrderMetrics(orders: Order[]): OrderMetrics {
  const orderCount = orders.length
  const totalSpent = orders.reduce((sum, order) => sum + order.total, 0)

  const counts = new Map<string, number>()
  for (const order of orders) {
    for (const name of order.restaurantNames) {
      counts.set(name, (counts.get(name) ?? 0) + 1)
    }
  }

  const favoriteRestaurant =
    Array.from(counts, ([name, count]) => ({ name, count })).sort(
      (a, b) => b.count - a.count || a.name.localeCompare(b.name)
    )[0]?.name ?? null

  return { orderCount, totalSpent, favoriteRestaurant }
}
