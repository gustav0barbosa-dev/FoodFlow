import type { Restaurant } from '@/types'

function normalize(value: string) {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

export function filterRestaurants(restaurants: Restaurant[], query: string) {
  const term = normalize(query.trim())
  if (!term) return restaurants

  return restaurants.filter(
    (restaurant) =>
      normalize(restaurant.name).includes(term) ||
      normalize(restaurant.category).includes(term)
  )
}
