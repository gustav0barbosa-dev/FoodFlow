import { Star, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Restaurant } from '@/types'
import { useEventsStore } from '@/store/eventsStore'
import { cn } from '@/lib/utils'

export function RestaurantCard({
  restaurant,
  size = 'lg',
  source = 'home_featured',
}: {
  restaurant: Restaurant
  size?: 'lg' | 'sm'
  source?: string
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
    <Link
      to={`/restaurante/${restaurant.id}`}
      onClick={handleClick}
      className={cn(
        'block bg-white rounded-2xl overflow-hidden shadow-sm border border-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
        isLarge ? 'w-60 shrink-0' : 'w-full'
      )}
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
        <h3 className="font-semibold text-ink truncate">{restaurant.name}</h3>
        <p className="text-xs text-ink-soft truncate">{restaurant.category}</p>
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
  )
}
