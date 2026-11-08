import { useState } from 'react'
import { SearchX } from 'lucide-react'
import { SearchBar } from '@/components/home/SearchBar'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'
import { SkeletonRow } from '@/components/common/SkeletonRow'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { useRestaurantSearch } from '@/hooks/useRestaurantSearch'
import { useSearchTracking } from '@/hooks/useSearchTracking'

const recentSearches = ['pizza', 'japonês', 'açaí', 'hambúrguer']

export function Search() {
  const [query, setQuery] = useState('')
  const { results, loading, error, retry } = useRestaurantSearch(query)

  useSearchTracking({
    query,
    results: results.length,
    source: 'search_page',
    enabled: !loading && !error,
  })

  return (
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <h1 className="font-display font-bold text-lg text-ink mb-3">Buscar</h1>
        <SearchBar value={query} onChange={setQuery} autoFocus />
      </header>

      <div className="px-4 mt-4">
        {!query && (
          <>
            <p className="text-sm font-medium text-ink mb-2">Buscas recentes</p>
            <div className="flex flex-wrap gap-2 mb-4">
              {recentSearches.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setQuery(s)}
                  aria-label={`Buscar por ${s}`}
                  className="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-sm text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}

        <div className="space-y-3" aria-busy={loading}>
          {loading &&
            Array.from({ length: 3 }).map((_, index) => <SkeletonRow key={index} />)}

          {!loading && error && (
            <ErrorState description={error} onAction={retry} />
          )}

          {!loading &&
            !error &&
            results.map((restaurant) => (
              <RestaurantCompactCard
                key={restaurant.id}
                restaurant={restaurant}
                source="search_results"
              />
            ))}

          {!loading && !error && results.length === 0 && (
            <EmptyState
              icon={SearchX}
              title="Nenhum restaurante encontrado"
              description="Tente outro termo ou revise a ortografia."
              className="py-10"
            />
          )}
        </div>
      </div>
    </div>
  )
}
