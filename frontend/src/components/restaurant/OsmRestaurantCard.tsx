import { Clock, ExternalLink, MapPin, Phone } from 'lucide-react'
import { HighlightMatch } from '@/components/common/HighlightMatch'
import { categoryLabel, formatOsmAddress } from '@/lib/osm'
import { cn } from '@/lib/utils'
import type { OsmRestaurant } from '@/types'

function websiteLabel(url: string) {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '')
}

export function OsmRestaurantCard({
  restaurant,
  query = '',
  selected = false,
  onSelect,
}: {
  restaurant: OsmRestaurant
  query?: string
  selected?: boolean
  onSelect: (restaurant: OsmRestaurant) => void
}) {
  const address = formatOsmAddress(restaurant.address)
  const categoryText = [categoryLabel(restaurant.category), restaurant.cuisine]
    .filter((value): value is string => Boolean(value))
    .join(' · ')

  return (
    <article
      className={cn(
        'bg-white rounded-2xl border shadow-sm overflow-hidden',
        selected
          ? 'border-primary ring-2 ring-primary/30'
          : 'border-gray-100'
      )}
    >
      <button
        type="button"
        onClick={() => onSelect(restaurant)}
        aria-pressed={selected}
        aria-label={`Ver detalhes de ${restaurant.name}`}
        className="w-full text-left p-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-ink truncate">
            <HighlightMatch text={restaurant.name} query={query} />
          </h3>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-soft shrink-0">
            OSM
          </span>
        </div>

        <p className="text-xs text-ink-soft truncate">
          <HighlightMatch text={categoryText} query={query} />
        </p>

        {address && (
          <p className="mt-1 text-xs text-ink-soft line-clamp-2 flex items-start gap-1">
            <MapPin
              size={12}
              className="shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <span>
              <HighlightMatch text={address} query={query} />
            </span>
          </p>
        )}

        <div className="mt-1 flex items-center justify-between text-xs text-ink-soft">
          {restaurant.distance_km !== null ? (
            <span>{restaurant.distance_km.toFixed(1)} km</span>
          ) : (
            <span />
          )}
          {!selected && (
            <span className="text-[10px] font-medium text-primary">
              Ver detalhes
            </span>
          )}
        </div>
      </button>

      {selected && (
        <div className="border-t border-gray-100 px-3 pb-3 pt-2 space-y-1.5 text-xs text-ink-soft">
          {restaurant.phone && (
            <a
              href={`tel:${restaurant.phone.replace(/[^\d+]/g, '')}`}
              className="flex items-center gap-1.5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
            >
              <Phone size={12} aria-hidden="true" />
              {restaurant.phone}
            </a>
          )}

          {restaurant.website && (
            <a
              href={restaurant.website}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
            >
              <ExternalLink size={12} aria-hidden="true" />
              <span className="truncate">
                {websiteLabel(restaurant.website)}
              </span>
            </a>
          )}

          {restaurant.opening_hours && (
            <p className="flex items-center gap-1.5">
              <Clock size={12} aria-hidden="true" />
              {restaurant.opening_hours}
            </p>
          )}

          {restaurant.osm_url && (
            <a
              href={restaurant.osm_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
            >
              <ExternalLink size={12} aria-hidden="true" />
              Ver no OpenStreetMap
            </a>
          )}

          {!restaurant.phone &&
            !restaurant.website &&
            !restaurant.opening_hours && (
              <p>
                Telefone, site e horário não cadastrados no OpenStreetMap.
              </p>
            )}
        </div>
      )}
    </article>
  )
}
