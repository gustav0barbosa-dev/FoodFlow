import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import type { Restaurant } from '@/types'
import { usePreferencesStore } from '@/store/preferencesStore'
import { countMatchingPreferences, matchesAnyPreference } from '@/lib/dietary'
import { RestaurantCard } from '@/components/restaurant/RestaurantCard'
import { Skeleton } from '@/components/common/Skeleton'

export function PreferenceMatches({
  restaurants,
  loading = false,
}: {
  restaurants: Restaurant[]
  loading?: boolean
}) {
  const preferences = usePreferencesStore((s) => s.preferences)

  if (preferences.length === 0) return null

  const matches = restaurants
    .filter((restaurant) => matchesAnyPreference(restaurant, preferences))
    .sort(
      (a, b) =>
        countMatchingPreferences(b, preferences) -
          countMatchingPreferences(a, preferences) || b.rating - a.rating
    )

  return (
    <section className="px-4 mt-4">
      <div className="flex items-center justify-between mb-1">
        <h2 className="font-display font-bold text-lg text-ink">Combina com você</h2>
        <Link
          to="/perfil"
          className="text-xs font-medium text-primary rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Ajustar
        </Link>
      </div>
      <p className="flex items-center gap-1 text-xs text-ink-soft mb-3">
        <Sparkles size={12} className="text-primary" aria-hidden="true" />
        {preferences.join(' · ')}
      </p>

      {loading ? (
        <div className="flex gap-3 overflow-x-auto no-scrollbar pb-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} variant="card" />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <p className="text-sm text-ink-soft py-4">
          Nenhuma opção com essas preferências por aqui ainda.
        </p>
      ) : (
        <div className="flex gap-3 overflow-x-auto no-scrollbar pb-2">
          {matches.map((restaurant) => (
            <RestaurantCard
              key={restaurant.id}
              restaurant={restaurant}
              source="home_preferences"
            />
          ))}
        </div>
      )}
    </section>
  )
}
