import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShoppingCart, MapPin } from 'lucide-react'
import { restaurants, categories, currentUser } from '@/data/mockData'
import { useCartStore } from '@/store/cartStore'
import { RestaurantCard } from '@/components/restaurant/RestaurantCard'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'
import { CategoryChip } from '@/components/restaurant/CategoryChip'
import { FilterChips } from '@/components/home/FilterChips'
import { SearchBar } from '@/components/home/SearchBar'
import { PreferenceMatches } from '@/components/home/PreferenceMatches'
import { Skeleton } from '@/components/common/Skeleton'
import { filterRestaurants } from '@/lib/search'
import {
  RESTAURANT_SORT_OPTIONS,
  sortRestaurants,
  type RestaurantSort,
} from '@/lib/sort'
import { useHomeFiltersStore } from '@/store/homeFiltersStore'
import { useSortStore } from '@/store/sortStore'
import { useSearchTracking } from '@/hooks/useSearchTracking'

export function Home() {
  const navigate = useNavigate()
  const count = useCartStore((s) => s.count())
  const [loading, setLoading] = useState(true)
  const sort = useSortStore((s) => s.sort)
  const setSort = useSortStore((s) => s.setSort)
  const filter = useHomeFiltersStore((s) => s.filter)
  const setFilter = useHomeFiltersStore((s) => s.setFilter)
  const category = useHomeFiltersStore((s) => s.category)
  const setCategory = useHomeFiltersStore((s) => s.setCategory)
  const resetFilters = useHomeFiltersStore((s) => s.resetFilters)
  const [query, setQuery] = useState('')
  const [loadedCount, setLoadedCount] = useState(3)
  const [recommendedLoadedCount, setRecommendedLoadedCount] = useState(3)
  const nearbyRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 500)
    return () => clearTimeout(t)
  }, [])

  const searched = filterRestaurants(restaurants, query)
  const filtered = searched.filter(
    (r) =>
      filter === 'Todos' || r.tags.some((t) => t.toLowerCase().includes(filter.toLowerCase()))
  )

  const nearby = sortRestaurants(
    filtered.filter((r) => !category || r.category === category),
    sort
  )

  useSearchTracking({ query, results: searched.length, source: 'home' })

  const handleCategory = (name: string) => {
    setCategory(category === name ? null : name)
    nearbyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-ink-soft">Olá, {currentUser.name.split(' ')[0]} 👋</p>
            <div className="flex items-center gap-1 text-sm font-medium text-ink">
              <MapPin size={14} className="text-primary" />
              {currentUser.location}
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate('/sacola')}
            className="relative w-10 h-10 rounded-full flex items-center justify-center hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label={
              count > 0
                ? `Abrir sacola com ${count} ${count === 1 ? 'item' : 'itens'}`
                : 'Abrir sacola'
            }
          >
            <ShoppingCart size={22} className="text-ink" />
            {count > 0 && (
              <span
                aria-hidden="true"
                className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-primary text-white text-[10px] font-semibold rounded-full flex items-center justify-center"
              >
                {count > 99 ? '99+' : count}
              </span>
            )}
          </button>
        </div>
        <div className="mt-3">
          <SearchBar value={query} onChange={setQuery} />
        </div>
      </header>

      {/* Recomendados */}
      <section className="px-4 mt-4">
        <h2 className="font-display font-bold text-lg text-ink mb-1">
          Recomendados para você
        </h2>
        <p className="text-xs text-ink-soft mb-3">Baseado no seu histórico e horário</p>
        <div className="flex gap-3 overflow-x-auto no-scrollbar pb-2">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} variant="card" />
              ))
            : filtered
                .filter((r) => r.isRecommended)
                .slice(0, recommendedLoadedCount)
                .map((r) => (
                  <RestaurantCard
                    key={r.id}
                    restaurant={r}
                    source="home_featured"
                    query={query}
                  />
                ))}
        </div>
        {!loading &&
          filtered.filter((r) => r.isRecommended).length > recommendedLoadedCount && (
          <button
            type="button"
            onClick={() =>
              setRecommendedLoadedCount((current) => current + 3)
            }
            className="mt-3 w-full py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Carregar mais ·{' '}
            {filtered.filter((r) => r.isRecommended).length -
              recommendedLoadedCount}
            restante{filtered.filter((r) => r.isRecommended).length -
              recommendedLoadedCount !== 1
              ? 's'
              : ''}
          </button>
        )}
      </section>

      {/* Combina com você */}
      <PreferenceMatches restaurants={filtered} loading={loading} />

      {/* Perto de você */}
      <section ref={nearbyRef} className="px-4 mt-4 scroll-mt-28">
        <h2 className="font-display font-bold text-lg text-ink mb-2">
          Perto de você
          {category && <span className="text-primary"> · {category}</span>}
        </h2>
        <FilterChips active={filter} onChange={setFilter} />
        <div className="mt-1 flex items-center justify-between gap-2">
          <label htmlFor="restaurant-sort" className="text-xs text-ink-soft">
            Ordenar por
          </label>
          <select
            id="restaurant-sort"
            value={sort}
            onChange={(event) => setSort(event.target.value as RestaurantSort)}
            className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {RESTAURANT_SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={resetFilters}
            className="text-xs font-medium text-primary px-2 py-1.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Limpar filtros
          </button>
        </div>
        <div className="space-y-3 mt-2">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} variant="card" />
              ))
            : nearby.slice(0, loadedCount).map((r) => (
                <RestaurantCompactCard
                  key={r.id}
                  restaurant={r}
                  source="home_nearby"
                  query={query}
                />
              ))}
          {!loading && nearby.length > loadedCount && (
            <button
              type="button"
              onClick={() => setLoadedCount((current) => current + 3)}
              className="w-full py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Carregar mais · {nearby.length - loadedCount} restante{nearby.length - loadedCount !== 1 ? 's' : ''}
            </button>
          )}
          {!loading && nearby.length === 0 && (
            <p className="text-center text-ink-soft text-sm py-6">
              {category
                ? `Nenhum restaurante de ${category} encontrado`
                : 'Nenhum restaurante encontrado'}
            </p>
          )}
        </div>
      </section>

      {/* Categorias */}
      <section className="px-4 mt-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-display font-bold text-lg text-ink">Categorias</h2>
          {category && (
            <button
              type="button"
              onClick={() => setCategory(null)}
              aria-label="Limpar filtro de categoria"
              className="text-xs font-medium text-primary rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Limpar
            </button>
          )}
        </div>
        <div className="grid grid-cols-4 gap-3">
          {categories.map((c) => (
            <CategoryChip
              key={c.id}
              emoji={c.emoji}
              name={c.name}
              active={category === c.name}
              onSelect={() => handleCategory(c.name)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}
