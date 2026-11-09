import { Star, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Restaurant } from '@/types'
import { useEventsStore } from '@/store/eventsStore'
import { FavoriteButton } from '@/components/restaurant/FavoriteButton'
import { HighlightMatch } from '@/components/common/HighlightMatch'
import { cn } from '@/lib/utils'

export function RestaurantCard({
  restaurant,
  size = 'lg',
  source = 'home_featured',
  query = '',
  className,
}: {
  restaurant: Restaurant
  size?: 'lg' | 'sm'
  source?: string
  query?: string
  className?: string
}) {
  const isLarge = size === 'lg'
  const trackEvent = useEventsStore((s) => s.trackEvent)

  const handleClick = () => {
    trackEvent('restaurant_card_clicked', {
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      source,
    })
  }

  return (
    <div
      className={cn(
        'relative bg-white rounded-2xl overflow-hidden shadow-sm border border-gray-100',
        className ?? (isLarge ? 'w-60 shrink-0' : 'w-full')
      )}
    >
      <Link
        to={`/restaurante/${restaurant.id}`}
        onClick={handleClick}
        className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <div className="relative">
          <img
            src={restaurant.image}
            alt={restaurant.name}
            className={cn('w-full object-cover', isLarge ? 'h-32' : 'h-40')}
          />
          {restaurant.isRecommended && (
            <span className="absolute top-2 left-2 bg-purple-600 text-white text-[10px] font-semibold px-2 py-1 rounded-full">
              ✨ Para você
            </span>
          )}
        </div>
        <div className="p-3">
          <h3 className="font-semibold text-ink truncate">
            <HighlightMatch text={restaurant.name} query={query} />
          </h3>
          <p className="text-xs text-ink-soft truncate">
            <HighlightMatch text={restaurant.category} query={query} />
          </p>
          <div className="flex items-center gap-2 mt-1.5 text-xs text-ink-soft">
            <span className="flex items-center gap-1">
              <Star size={12} className="text-star fill-star" />
              {restaurant.rating}
            </span>
            <span className="flex items-center gap-1">
              <MapPin size={12} />
              {restaurant.distanceKm.toFixed(1)} km
            </span>
            <span>
              {restaurant.deliveryTimeMin}-{restaurant.deliveryTimeMax} min
            </span>
          </div>
        </div>
      </Link>

      <FavoriteButton restaurant={restaurant} className="absolute top-2 right-2" />
    </div>
  )
}
