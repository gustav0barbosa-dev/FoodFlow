export interface MenuItem {
  id: string
  name: string
  description: string
  price: number
  image: string
}

export interface Review {
  id: string
  userName: string
  rating: number
  date: string
  comment: string
  userId?: string
}

export const DIETARY_PREFERENCES = [
  'Vegano',
  'Vegetariano',
  'Sem glúten',
  'Sem lactose',
] as const

export type DietaryPreference = (typeof DIETARY_PREFERENCES)[number]

export type RestaurantSource = 'foodflow' | 'osm'

export interface Restaurant {
  id: string
  name: string
  category: string
  image: string
  rating: number
  reviewCount: number
  distanceKm: number
  deliveryFee: number
  deliveryTimeMin: number
  deliveryTimeMax: number
  address: string
  phone: string
  tags: string[]
  dietaryTags: DietaryPreference[]
  isRecommended: boolean
  menu: MenuItem[]
  reviews: Review[]
  hours: string
  paymentMethods: string[]
  /** Origem do registro. Ausente equivale ao catálogo próprio (foodflow). */
  source?: RestaurantSource
  osmType?: 'node' | 'way' | 'relation'
  osmId?: number
  latitude?: number
  longitude?: number
  cuisine?: string
  website?: string
  openingHours?: string
  osmUrl?: string
}

export type NearbyCategory = 'restaurant' | 'fast_food' | 'cafe' | 'bar'

export interface OsmAddress {
  street: string | null
  number: string | null
  city: string | null
  postcode: string | null
}

/**
 * Estabelecimento descoberto no OpenStreetMap via Overpass API.
 *
 * Não é um restaurante do catálogo do FoodFlow: não possui cardápio, taxa ou
 * tempo de entrega. O par `osm_type`/`osm_id` é o identificador externo.
 */
export interface OsmRestaurant {
  osm_id: number
  osm_type: 'node' | 'way' | 'relation'
  name: string
  latitude: number
  longitude: number
  category: string | null
  cuisine: string | null
  address: OsmAddress | null
  phone: string | null
  website: string | null
  opening_hours: string | null
  osm_url: string | null
  dietary_tags?: string[]
  distance_km: number | null
}

export interface NearbyRestaurantsResponse {
  source: string
  count: number
  restaurants: OsmRestaurant[]
}

export interface CartLine {
  restaurantId: string
  restaurantName: string
  item: MenuItem
  quantity: number
}