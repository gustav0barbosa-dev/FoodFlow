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
import { SkeletonCard } from '@/components/common/SkeletonCard'

export function Home() {
  const navigate = useNavigate()
  const count = useCartStore((s) => s.count())
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('Todos')
  const [category, setCategory] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const nearbyRef = useRef<HTMLElement>(null)

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

  const nearby = filtered.filter((r) => !category || r.category === category)

  const handleCategory = (name: string) => {
    setCategory((current) => (current === name ? null : name))
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
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : filtered
                .filter((r) => r.isRecommended)
                .map((r) => (
                  <RestaurantCard key={r.id} restaurant={r} source="home_featured" />
                ))}
        </div>
      </section>

      {/* Perto de você */}
      <section ref={nearbyRef} className="px-4 mt-4 scroll-mt-28">
        <h2 className="font-display font-bold text-lg text-ink mb-2">
          Perto de você
          {category && <span className="text-primary"> · {category}</span>}
        </h2>
        <FilterChips active={filter} onChange={setFilter} />
        <div className="space-y-3 mt-2">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : nearby.map((r) => (
                <RestaurantCompactCard key={r.id} restaurant={r} source="home_nearby" />
              ))}
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
