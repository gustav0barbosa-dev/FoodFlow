import type { DietaryPreference, Restaurant } from '@/types'

export function countMatchingPreferences(
  restaurant: Restaurant,
  preferences: DietaryPreference[]
) {
  return preferences.filter((preference) =>
    restaurant.dietaryTags.includes(preference)
  ).length
}

export function matchesAnyPreference(
  restaurant: Restaurant,
  preferences: DietaryPreference[]
) {
  return preferences.some((preference) =>
    restaurant.dietaryTags.includes(preference)
  )
}
