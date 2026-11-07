import { useEffect, useState } from 'react'
import { ShoppingCart, MapPin } from 'lucide-react'
import { restaurants, categories, currentUser } from '@/data/mockData'
import { RestaurantCard } from '@/components/restaurant/RestaurantCard'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'
import { CategoryChip } from '@/components/restaurant/CategoryChip'
import { FilterChips } from '@/components/home/FilterChips'
import { SearchBar } from '@/components/home/SearchBar'
import { SkeletonCard } from '@/components/common/SkeletonCard'

export function Home() {
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('Todos')
  const [query, setQuery] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 500)
    return () => clearTimeout(t)
  }, [])

  const filtered = restaurants.filter((r) => {
    const matchesQuery =
      !query ||
      r.name.toLowerCase().includes(query.toLowerCase()) ||
      r.category.toLowerCase().includes(query.toLowerCase())
    const matchesFilter =
      filter === 'Todos' || r.tags.some((t) => t.toLowerCase().includes(filter.toLowerCase()))
    return matchesQuery && matchesFilter
  })

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
          <button className="relative">
            <ShoppingCart size={22} className="text-ink" />
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
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : filtered
                .filter((r) => r.isRecommended)
                .map((r) => <RestaurantCard key={r.id} restaurant={r} />)}
        </div>
      </section>

      {/* Perto de você */}
      <section className="px-4 mt-4">
        <h2 className="font-display font-bold text-lg text-ink mb-2">Perto de você</h2>
        <FilterChips active={filter} onChange={setFilter} />
        <div className="space-y-3 mt-2">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : filtered.map((r) => <RestaurantCompactCard key={r.id} restaurant={r} />)}
          {!loading && filtered.length === 0 && (
            <p className="text-center text-ink-soft text-sm py-6">
              Nenhum restaurante encontrado
            </p>
          )}
        </div>
      </section>

      {/* Categorias */}
      <section className="px-4 mt-6">
        <h2 className="font-display font-bold text-lg text-ink mb-2">Categorias</h2>
        <div className="grid grid-cols-4 gap-3">
          {categories.map((c) => (
            <CategoryChip key={c.id} emoji={c.emoji} name={c.name} />
          ))}
        </div>
      </section>
    </div>
  )
}