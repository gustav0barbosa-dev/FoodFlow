import { Heart } from 'lucide-react'
import type { Restaurant } from '@/types'
import { useFavoritesStore } from '@/store/favoritesStore'
import { useEventsStore } from '@/store/eventsStore'
import { cn } from '@/lib/utils'

export function FavoriteButton({
  restaurant,
  className,
}: {
  restaurant: Restaurant
  className?: string
}) {
  const isFavorite = useFavoritesStore((s) => s.favoriteIds.includes(restaurant.id))
  const toggleFavorite = useFavoritesStore((s) => s.toggleFavorite)
  const trackEvent = useEventsStore((s) => s.trackEvent)

  const handleToggle = () => {
    toggleFavorite(restaurant.id)
    trackEvent('favorite_toggled', {
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      action: isFavorite ? 'removed' : 'added',
    })
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      aria-pressed={isFavorite}
      aria-label={
        isFavorite
          ? `Remover ${restaurant.name} dos favoritos`
          : `Adicionar ${restaurant.name} aos favoritos`
      }
      className={cn(
        'w-8 h-8 rounded-full bg-white/90 shadow flex items-center justify-center transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
        className
      )}
    >
      <Heart
        size={16}
        className={cn(isFavorite ? 'text-primary fill-primary' : 'text-ink-soft')}
      />
    </button>
  )
}
