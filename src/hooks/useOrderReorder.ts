import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { restaurants } from '@/data/mockData'
import { useCartStore } from '@/store/cartStore'
import type { Order } from '@/store/ordersStore'

export function useOrderReorder() {
  const addItem = useCartStore((s) => s.addItem)
  const navigate = useNavigate()

  return (order: Order) => {
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
}
