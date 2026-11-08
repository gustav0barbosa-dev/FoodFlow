import { Star, MapPin, Bike } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Restaurant } from '@/types'
import { useEventsStore } from '@/store/eventsStore'
import { FavoriteButton } from '@/components/restaurant/FavoriteButton'
import { HighlightMatch } from '@/components/common/HighlightMatch'
import { getMatchingMenuItems } from '@/lib/search'
import { formatBRL } from '@/lib/utils'

export function RestaurantCompactCard({
  restaurant,
  source = 'home_nearby',
  query = '',
}: {
  restaurant: Restaurant
  source?: string
  query?: string
}) {
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const matchingItems = getMatchingMenuItems(restaurant, query)

  const handleClick = () => {
    trackEvent('restaurant_card_clicked', {
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      source,
    })
  }

  return (
    <div className="relative">
      <Link
        to={`/restaurante/${restaurant.id}`}
        onClick={handleClick}
        className="flex gap-3 bg-white rounded-2xl p-3 pr-11 border border-gray-100 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <img
          src={restaurant.image}
          alt={restaurant.name}
          className="w-20 h-20 rounded-xl object-cover shrink-0"
        />
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-ink truncate">
            <HighlightMatch text={restaurant.name} query={query} />
          </h3>
          <p className="text-xs text-ink-soft truncate">
            <HighlightMatch text={restaurant.category} query={query} />
          </p>
          {matchingItems.length > 0 && (
            <p
              className="mt-1 text-xs text-ink-soft truncate"
              title={matchingItems.map((item) => item.name).join(', ')}
            >
              <span className="font-medium text-primary-dark">Pratos: </span>
              {matchingItems.slice(0, 2).map((item, index) => (
                <span key={item.id}>
                  {index > 0 && ', '}
                  <HighlightMatch text={item.name} query={query} />
                </span>
              ))}
              {matchingItems.length > 2 && (
                <span> +{matchingItems.length - 2}</span>
              )}
            </p>
          )}
          <div className="flex items-center gap-2 mt-1 text-xs text-ink-soft">
            <span className="flex items-center gap-1">
              <Star size={12} className="text-star fill-star" />
              {restaurant.rating}
            </span>
            <span className="flex items-center gap-1">
              <MapPin size={12} />
              {restaurant.distanceKm.toFixed(1)} km
            </span>
            <span className="flex items-center gap-1">
              <Bike size={12} />
              {restaurant.deliveryFee === 0 ? 'Grátis' : formatBRL(restaurant.deliveryFee)}
            </span>
          </div>
        </div>
      </Link>

      <FavoriteButton restaurant={restaurant} className="absolute top-2 right-2" />
    </div>
  )
}
