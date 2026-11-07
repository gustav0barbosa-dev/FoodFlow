import { useState } from 'react'
import { restaurants } from '@/data/mockData'
import { SearchBar } from '@/components/home/SearchBar'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'

const recentSearches = ['pizza', 'japonês', 'açaí', 'hambúrguer']

export function Search() {
  const [query, setQuery] = useState('')

  const results = restaurants.filter(
    (r) =>
      !query ||
      r.name.toLowerCase().includes(query.toLowerCase()) ||
      r.category.toLowerCase().includes(query.toLowerCase())
  )

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
                  onClick={() => setQuery(s)}
                  className="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-sm text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}

        <div className="space-y-3">
          {results.map((r) => (
            <RestaurantCompactCard key={r.id} restaurant={r} />
          ))}
          {results.length === 0 && (
            <p className="text-center text-ink-soft text-sm py-10">
              Nenhum restaurante encontrado
            </p>
          )}
        </div>
      </div>
    </div>
  )
}