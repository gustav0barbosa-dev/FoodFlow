/** Utilitários de exibição para dados do OpenStreetMap. */

import type { NearbyCategory, OsmAddress, OsmRestaurant } from '@/types'
import type { RestaurantSort } from '@/lib/sort'
import { matchesQuery } from '@/lib/search'

export const OSM_TILE_URL =
  'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

export const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright'

export const OSM_ATTRIBUTION = '© OpenStreetMap contributors'

export const OSM_ATTRIBUTION_HTML =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export const NEARBY_CATEGORY_OPTIONS: Array<{
  value: NearbyCategory | ''
  label: string
}> = [
  { value: '', label: 'Todas as categorias' },
  { value: 'restaurant', label: 'Restaurantes' },
  { value: 'fast_food', label: 'Fast food' },
  { value: 'cafe', label: 'Cafés' },
  { value: 'bar', label: 'Bares' },
]

const CATEGORY_LABELS: Record<string, string> = {
  restaurant: 'Restaurante',
  fast_food: 'Fast food',
  cafe: 'Café',
  bar: 'Bar',
}

export function categoryLabel(category: string | null): string {
  if (!category) return 'Restaurante'
  return CATEGORY_LABELS[category] ?? category
}

/** Identificador estável para o marcador e para a lista. */
export function osmKey(
  restaurant: Pick<OsmRestaurant, 'osm_type' | 'osm_id'>
): string {
  return `${restaurant.osm_type}/${restaurant.osm_id}`
}

/** Rota da tela de detalhes compartilhada com o catálogo próprio. */
export function osmDetailPath(
  restaurant: Pick<OsmRestaurant, 'osm_type' | 'osm_id'>
): string {
  return `/restaurante/osm/${restaurant.osm_type}/${restaurant.osm_id}`
}

export function formatOsmAddress(address: OsmAddress | null): string {
  if (!address) return ''

  const street = [address.street, address.number]
    .filter((value): value is string => Boolean(value))
    .join(', ')

  return [street, address.city, address.postcode]
    .filter((value): value is string => Boolean(value))
    .join(' · ')
}

/** Texto único para busca local nos resultados do OSM. */
export function osmSearchText(restaurant: OsmRestaurant): string {
  return [
    restaurant.name,
    restaurant.category,
    restaurant.cuisine,
    formatOsmAddress(restaurant.address),
    ...(restaurant.dietary_tags ?? []),
  ]
    .filter((value): value is string => Boolean(value))
    .join(' ')
}

/** Rótulos exibidos/filtráveis de um restaurante do OSM. */
export function osmTags(restaurant: OsmRestaurant): string[] {
  return [
    categoryLabel(restaurant.category),
    restaurant.cuisine ?? '',
    ...(restaurant.dietary_tags ?? []),
  ].filter((value): value is string => Boolean(value))
}

/**
 * Ordena resultados do OSM com o mesmo contrato do catálogo.
 *
 * O OSM não fornece avaliação nem frete; nesses critérios usamos o nome como
 * desempate estável em vez de inventar valores.
 */
export function sortOsmRestaurants(
  restaurants: OsmRestaurant[],
  sort: RestaurantSort
): OsmRestaurant[] {
  const sorted = [...restaurants]
  switch (sort) {
    case 'distance':
      return sorted.sort(
        (a, b) =>
          (a.distance_km ?? Infinity) - (b.distance_km ?? Infinity) ||
          a.name.localeCompare(b.name)
      )
    case 'rating':
    case 'deliveryFee':
      return sorted.sort((a, b) => a.name.localeCompare(b.name))
    default:
      return sorted
  }
}

export interface OsmFilters {
  query?: string
  cuisine?: string
  maxDistanceKm?: number | null
  /** Chip ativo: 'Todos', 'Vegano', etc. */
  chip?: string
  sort?: RestaurantSort
}

/**
 * Aplica ao OSM o mesmo contrato de filtros do catálogo.
 *
 * Frete e avaliação não existem no OSM; nesses critérios a ordenação usa o
 * nome, sem inventar valores.
 */
export function filterOsmRestaurants(
  restaurants: OsmRestaurant[],
  {
    query = '',
    cuisine = '',
    maxDistanceKm = null,
    chip = 'Todos',
    sort = 'recommended',
  }: OsmFilters = {}
): OsmRestaurant[] {
  const term = query.trim()
  const filtered = restaurants
    .filter(
      (restaurant) =>
        !term || matchesQuery(osmSearchText(restaurant), query)
    )
    .filter(
      (restaurant) => !cuisine || restaurant.cuisine === cuisine
    )
    .filter(
      (restaurant) =>
        maxDistanceKm === null ||
        (restaurant.distance_km ?? Number.POSITIVE_INFINITY) <= maxDistanceKm
    )
    .filter((restaurant) => {
      if (chip === 'Todos') return true
      if (chip === 'Vegano') {
        return (restaurant.dietary_tags ?? []).includes('Vegano')
      }
      return osmTags(restaurant).some((tag) =>
        tag.toLowerCase().includes(chip.toLowerCase())
      )
    })

  return sortOsmRestaurants(filtered, sort)
}
