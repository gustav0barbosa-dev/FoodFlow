import { CircleMarker, Popup } from 'react-leaflet'
import {
  categoryLabel,
  formatOsmAddress,
  OSM_ATTRIBUTION,
} from '@/lib/osm'
import type { OsmRestaurant } from '@/types'

export function RestaurantMarker({
  restaurant,
  selected,
  onSelect,
}: {
  restaurant: OsmRestaurant
  selected: boolean
  onSelect: (restaurant: OsmRestaurant) => void
}) {
  const address = formatOsmAddress(restaurant.address)

  return (
    <CircleMarker
      center={[restaurant.latitude, restaurant.longitude]}
      radius={selected ? 11 : 8}
      pathOptions={{
        color: '#ea1d2c',
        fillColor: '#ea1d2c',
        fillOpacity: selected ? 0.9 : 0.6,
        weight: 2,
      }}
      eventHandlers={{ click: () => onSelect(restaurant) }}
    >
      <Popup>
        <div className="space-y-0.5 text-xs">
          <strong>{restaurant.name}</strong>
          <p>{categoryLabel(restaurant.category)}</p>
          {address && <p>{address}</p>}
          {restaurant.opening_hours && <p>{restaurant.opening_hours}</p>}
          <p className="text-[10px] text-gray-500">{OSM_ATTRIBUTION}</p>
        </div>
      </Popup>
    </CircleMarker>
  )
}
