import type { Restaurant } from '@/types'

export type RestaurantSort = 'recommended' | 'rating' | 'deliveryFee' | 'distance'

export const RESTAURANT_SORT_OPTIONS: {
  value: RestaurantSort
  label: string
}[] = [
  { value: 'recommended', label: 'Recomendados' },
  { value: 'rating', label: 'Mais bem avaliados' },
  { value: 'deliveryFee', label: 'Menor frete' },
  { value: 'distance', label: 'Mais próximo' },
]

const sorters: Record<RestaurantSort, (a: Restaurant, b: Restaurant) => number> = {
  recommended: () => 0,
  rating: (a, b) => b.rating - a.rating || a.name.localeCompare(b.name),
  deliveryFee: (a, b) => a.deliveryFee - b.deliveryFee || b.rating - a.rating,
  distance: (a, b) => a.distanceKm - b.distanceKm || b.rating - a.rating,
}

export function sortRestaurants(
  restaurants: Restaurant[],
  sort: RestaurantSort
): Restaurant[] {
  if (sort === 'recommended') return restaurants
  return [...restaurants].sort(sorters[sort])
}
