import { Plus } from 'lucide-react'
import type { MenuItem as MenuItemType } from '@/types'
import { formatBRL } from '@/lib/utils'
import { useCartStore } from '@/store/cartStore'
import { useEventsStore } from '@/store/eventsStore'
import { toast } from 'sonner'

export function MenuItem({
  item,
  restaurantId,
  restaurantName,
}: {
  item: MenuItemType
  restaurantId: string
  restaurantName: string
}) {
  const addItem = useCartStore((s) => s.addItem)
  const trackEvent = useEventsStore((s) => s.trackEvent)

  const handleAdd = () => {
    addItem(restaurantId, restaurantName, item)
    trackEvent('add_to_cart', {
      restaurantId,
      restaurantName,
      itemId: item.id,
      itemName: item.name,
      price: item.price,
    })
    toast.success('Adicionado ao carrinho')
  }

  return (
    <div className="flex gap-3 py-3 border-b border-gray-100">
      <div className="flex-1">
        <h4 className="font-medium text-ink">{item.name}</h4>
        <p className="text-xs text-ink-soft mt-0.5">{item.description}</p>
        <span className="text-sm font-semibold text-primary mt-1 block">
          {formatBRL(item.price)}
        </span>
      </div>
      <div className="relative">
        <img src={item.image} alt={item.name} className="w-20 h-20 rounded-xl object-cover" />
        <button
          onClick={handleAdd}
          className="absolute -bottom-1 -right-1 bg-primary text-white rounded-full w-7 h-7 flex items-center justify-center shadow"
          aria-label={`Adicionar ${item.name}`}
        >
          <Plus size={16} />
        </button>
      </div>
    </div>
  )
}