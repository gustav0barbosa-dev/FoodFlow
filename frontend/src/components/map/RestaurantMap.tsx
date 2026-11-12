import { useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { RestaurantMarker } from '@/components/map/RestaurantMarker'
import { osmKey, OSM_ATTRIBUTION_HTML, OSM_TILE_URL } from '@/lib/osm'
import type { OsmRestaurant } from '@/types'

function Recenter({ lat, lon }: { lat: number; lon: number }) {
  const map = useMap()

  useEffect(() => {
    map.setView([lat, lon])
  }, [map, lat, lon])

  return null
}

/**
 * Mapa dos restaurantes descobertos no OpenStreetMap.
 *
 * Não recarrega a consulta ao mover o mapa: a busca só muda quando a
 * localização do usuário ou a categoria selecionada mudam.
 */
export function RestaurantMap({
  restaurants,
  center,
  selectedKey,
  onSelect,
}: {
  restaurants: OsmRestaurant[]
  center: { lat: number; lon: number }
  selectedKey: string | null
  onSelect: (restaurant: OsmRestaurant) => void
}) {
  return (
    <div
      role="region"
      aria-label="Mapa de restaurantes próximos"
      className="overflow-hidden rounded-2xl border border-gray-200"
    >
      <MapContainer
        center={[center.lat, center.lon]}
        zoom={14}
        scrollWheelZoom={false}
        style={{ height: '320px', width: '100%' }}
      >
        <TileLayer
          attribution={OSM_ATTRIBUTION_HTML}
          url={OSM_TILE_URL}
        />
        <Recenter lat={center.lat} lon={center.lon} />
        {restaurants.map((restaurant) => (
          <RestaurantMarker
            key={osmKey(restaurant)}
            restaurant={restaurant}
            selected={selectedKey === osmKey(restaurant)}
            onSelect={onSelect}
          />
        ))}
      </MapContainer>
    </div>
  )
}
