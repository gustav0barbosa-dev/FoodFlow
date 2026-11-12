import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShoppingCart, MapPin } from 'lucide-react'
import { categories, currentUser } from '@/data/mockData'
import { useCartStore } from '@/store/cartStore'
import { useLocationStore } from '@/store/locationStore'
import { RestaurantCard } from '@/components/restaurant/RestaurantCard'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'
import { OsmRestaurantCard } from '@/components/restaurant/OsmRestaurantCard'
import { RestaurantMap } from '@/components/map/RestaurantMap'
import { CategoryChip } from '@/components/restaurant/CategoryChip'
import { FilterChips } from '@/components/home/FilterChips'
import { SearchBar } from '@/components/home/SearchBar'
import { PreferenceMatches } from '@/components/home/PreferenceMatches'
import { Skeleton } from '@/components/common/Skeleton'
import { filterRestaurants } from '@/lib/search'
import {
  NEARBY_CATEGORY_OPTIONS,
  OSM_ATTRIBUTION,
  OSM_COPYRIGHT_URL,
  filterOsmRestaurants,
  osmDetailPath,
  osmKey,
} from '@/lib/osm'
import type { NearbyCategory, OsmRestaurant } from '@/types'
import {
  RESTAURANT_SORT_OPTIONS,
  sortRestaurants,
  type RestaurantSort,
} from '@/lib/sort'
import { cn } from '@/lib/utils'
import { useHomeFiltersStore } from '@/store/homeFiltersStore'
import { useHomeSearchStore } from '@/store/homeSearchStore'
import { useSortStore } from '@/store/sortStore'
import { useAuthStore } from '@/store/authStore'
import { useCatalogStore } from '@/store/catalogStore'
import { trackInteraction } from '@/lib/interactions'
import { useCatalog } from '@/hooks/useCatalog'
import { useNearbyRestaurants } from '@/hooks/useNearbyRestaurants'
import { useRecommendations } from '@/hooks/useRecommendations'
import { useSearchTracking } from '@/hooks/useSearchTracking'

const EXPERIMENT_LABELS: Record<string, string> = {
  baseline: 'Baseline (popularidade)',
  personalized: 'Recomendações personalizadas',
  distance: 'Por distância',
}

export function Home() {
  const navigate = useNavigate()
  const count = useCartStore((s) => s.count())
  const { restaurants, error: catalogError } = useCatalog()
  const { recommended, loading: recommendationsLoading, experimentGroup } =
    useRecommendations(restaurants)
  const recommendationContext = useCatalogStore(
    (s) => s.recommendationContext
  )
  const [dismissedIds, setDismissedIds] = useState<string[]>([])
  const trackedImpressions = useRef('')
  const lat = useLocationStore((s) => s.lat)
  const lon = useLocationStore((s) => s.lon)
  const locationLabel = useLocationStore((s) => s.label)
  const [osmCategory, setOsmCategory] = useState<NearbyCategory | ''>('')
  const [osmCuisine, setOsmCuisine] = useState('')
  const [selectedOsmKey, setSelectedOsmKey] = useState<string | null>(null)
  const {
    restaurants: osmRestaurants,
    loading: osmLoading,
    error: osmError,
  } = useNearbyRestaurants({
    category: osmCategory || undefined,
  })
  const authName = useAuthStore((s) => s.user?.name)
  const greetingName = (authName?.trim() || currentUser.name).split(' ')[0]
  const [loading, setLoading] = useState(true)
  const sort = useSortStore((s) => s.sort)
  const setSort = useSortStore((s) => s.setSort)
  const filter = useHomeFiltersStore((s) => s.filter)
  const setFilter = useHomeFiltersStore((s) => s.setFilter)
  const category = useHomeFiltersStore((s) => s.category)
  const setCategory = useHomeFiltersStore((s) => s.setCategory)
  const resetFilters = useHomeFiltersStore((s) => s.resetFilters)
  const handleResetFilters = () => {
    resetFilters()
    setMaxDistance(null)
    setOsmCategory('')
    setOsmCuisine('')
  }
  const [loadedCount, setLoadedCount] = useState(3)
  const [recommendedLoadedCount, setRecommendedLoadedCount] = useState(3)
  const query = useHomeSearchStore((s) => s.query)
  const setQuery = useHomeSearchStore((s) => s.setQuery)
  const [maxDistance, setMaxDistance] = useState<number | null>(null)
  const nearbyRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 500)
    return () => clearTimeout(t)
  }, [])

  // Impressão = o restaurante foi efetivamente exibido no ranking. Enviamos
  // uma vez por combinação (grupo, versão, lista) para não inflar as métricas
  // do experimento A/B a cada re-render.
  useEffect(() => {
    if (recommendationsLoading || !recommendationContext) return
    const visible = recommended.filter(
      (restaurant) => !dismissedIds.includes(restaurant.id)
    )
    if (visible.length === 0) return

    const signature = [
      recommendationContext.experimentMode,
      recommendationContext.experimentVersion,
      recommendationContext.recommendationId,
      recommendationContext.experimentGroup,
      recommendationContext.modelVersion,
      visible.map((restaurant) => restaurant.id).join(','),
    ].join('|')
    if (trackedImpressions.current === signature) return
    trackedImpressions.current = signature

    visible.forEach((restaurant, index) => {
      trackInteraction(restaurant.id, 'IMPRESSION', {
        experimentGroup: recommendationContext.experimentGroup,
        experimentMode: recommendationContext.experimentMode,
        experimentVersion: recommendationContext.experimentVersion,
        recommendationId: recommendationContext.recommendationId,
        recommendationPosition: index,
        modelVersion: recommendationContext.modelVersion,
        metadata: { source: 'home_featured' },
      })
    })
  }, [
    recommendationsLoading,
    recommendationContext,
    recommended,
    dismissedIds,
  ])

  const handleDismiss = (restaurant: (typeof recommended)[number]) => {
    setDismissedIds((current) =>
      current.includes(restaurant.id) ? current : [...current, restaurant.id]
    )
  }

  const matchesFilter = (restaurant: (typeof restaurants)[number]) =>
    filter === 'Todos' ||
    restaurant.tags.some((tag) =>
      tag.toLowerCase().includes(filter.toLowerCase())
    )

  const osmFiltered = useMemo(
    () =>
      filterOsmRestaurants(osmRestaurants, {
        query,
        cuisine: osmCuisine,
        maxDistanceKm: maxDistance,
        chip: filter,
        sort,
      }),
    [osmRestaurants, query, osmCuisine, maxDistance, filter, sort]
  )

  const osmCuisines = useMemo(() => {
    const values = new Set<string>()
    for (const restaurant of osmRestaurants) {
      if (restaurant.cuisine) values.add(restaurant.cuisine)
    }
    return [...values].sort((a, b) => a.localeCompare(b))
  }, [osmRestaurants])
  const handleSelectOsm = (restaurant: OsmRestaurant) => {
    setSelectedOsmKey(osmKey(restaurant))
    // O clique no card/marcador é uma interação CLICK; a tela de detalhes
    // registra o VIEW depois de carregar o restaurante persistido.
    navigate(osmDetailPath(restaurant), {
      state: { interaction: 'CLICK' },
    })
  }

  const handleOsmCategory = (value: NearbyCategory | '') => {
    setOsmCategory(value)
    setSelectedOsmKey(null)
  }

  const searched = filterRestaurants(restaurants, query)
  const filtered = searched.filter(matchesFilter)
  const recommendedFiltered = filterRestaurants(recommended, query)
    .filter(matchesFilter)
    .filter((restaurant) => !dismissedIds.includes(restaurant.id))

  const nearby = sortRestaurants(
    filtered
      .filter((r) => !category || r.category === category)
      .filter((r) => maxDistance === null || r.distanceKm <= maxDistance),
    sort
  )

  useSearchTracking({ query, results: searched.length, source: 'home' })

  const handleCategory = (name: string) => {
    setCategory(category === name ? null : name)
    nearbyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="h-full overflow-y-auto pb-6 bg-surface-muted">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white px-4 pt-4 pb-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-ink-soft">Olá, {greetingName} 👋</p>
            <div className="flex items-center gap-1 text-sm font-medium text-ink">
              <MapPin size={14} className="text-primary" />
              {locationLabel}
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

      {/* Aviso de fallback: deixa claro quando o catálogo local está em uso. */}
      {catalogError && (
        <div
          role="status"
          className="mx-4 mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          {catalogError}
        </div>
      )}

      {/* Recomendados */}
      <section className="px-4 mt-4">
        <h2 className="font-display font-bold text-lg text-ink mb-1">
          Recomendados para você
        </h2>
        <p className="text-xs text-ink-soft mb-3">Baseado no seu histórico e horário</p>
        {experimentGroup && (
          <p className="text-[10px] text-ink-soft mb-3">
            Experimento A/B:{' '}
            <span className="font-medium text-ink">
              {EXPERIMENT_LABELS[experimentGroup] ?? experimentGroup}
            </span>
            {recommendationContext?.experimentMode === 'demo' && (
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                Modo demonstração — não conta nas métricas oficiais
              </span>
            )}
          </p>
        )}
        <div
          className={cn(
            // Mobile: carrossel horizontal.
            'flex gap-3 overflow-x-auto no-scrollbar pb-2',
            // Tablet/Desktop: grid de cards.
            'sm:grid sm:grid-cols-2 lg:grid-cols-3 sm:gap-4 sm:pb-0'
          )}
        >
          {recommendationsLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} variant="card" className="w-60 sm:w-full" />
              ))
            : recommendedFiltered
                .slice(0, recommendedLoadedCount)
                .map((r) => (
                  <RestaurantCard
                    key={r.id}
                    restaurant={r}
                    source="home_featured"
                    query={query}
                    className="w-full"
                    onDismiss={handleDismiss}
                  />
                ))}
        </div>
        {!recommendationsLoading &&
          recommendedFiltered.length > recommendedLoadedCount && (
          <button
            type="button"
            onClick={() =>
              setRecommendedLoadedCount((current) => current + 3)
            }
            className="mt-3 w-full py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Carregar mais ·{' '}
            {recommendedFiltered.length - recommendedLoadedCount}
            restante{recommendedFiltered.length - recommendedLoadedCount !== 1
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
            onClick={handleResetFilters}
            className="text-xs font-medium text-primary px-2 py-1.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Limpar filtros
          </button>
        </div>
        <div className="mt-1 flex items-center justify-between gap-2">
          <label htmlFor="restaurant-distance" className="text-xs text-ink-soft">
            Raio máximo
          </label>
          <select
            id="restaurant-distance"
            value={maxDistance ?? ''}
            onChange={(event) =>
              setMaxDistance(
                event.target.value === '' ? null : Number(event.target.value)
              )
            }
            className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <option value="">Sem limite</option>
            <option value="1">1 km</option>
            <option value="3">3 km</option>
            <option value="5">5 km</option>
            <option value="10">10 km</option>
          </select>
        </div>
        <div
          className={cn(
            // Mobile: lista vertical.
            'space-y-3 mt-2',
            // Tablet/Desktop: grid de 2 colunas.
            'sm:grid sm:grid-cols-2 sm:gap-3'
          )}
        >
          {loading
            ? Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} variant="card" className="w-full" />
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

      {/* Restaurantes reais via OpenStreetMap (camada de descoberta) */}
      <section className="px-4 mt-6">
        <div className="flex items-center justify-between gap-2 mb-1">
          <h2 className="font-display font-bold text-lg text-ink">
            Restaurantes reais perto de você
          </h2>
          <span className="text-[10px] font-semibold uppercase tracking-wide text-ink-soft">
            OpenStreetMap
          </span>
        </div>
        <p className="text-xs text-ink-soft mb-2">
          Descobertos via Overpass API · cardápio e entrega não disponíveis no
          FoodFlow
        </p>

        <div className="flex items-center justify-between gap-2 mb-2">
          <label htmlFor="osm-category" className="text-xs text-ink-soft">
            Categoria
          </label>
          <select
            id="osm-category"
            value={osmCategory}
            onChange={(event) =>
              handleOsmCategory(event.target.value as NearbyCategory | '')
            }
            className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            {NEARBY_CATEGORY_OPTIONS.map((option) => (
              <option key={option.value || 'all'} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-between gap-2 mb-2">
          <label htmlFor="osm-cuisine" className="text-xs text-ink-soft">
            Culinária
          </label>
          <select
            id="osm-cuisine"
            value={osmCuisine}
            onChange={(event) => {
              setOsmCuisine(event.target.value)
              setSelectedOsmKey(null)
            }}
            className="rounded-xl border border-gray-200 bg-white px-2 py-1.5 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <option value="">Todas as culinárias</option>
            {osmCuisines.map((cuisine) => (
              <option key={cuisine} value={cuisine}>
                {cuisine}
              </option>
            ))}
          </select>
        </div>

        <FilterChips active={filter} onChange={setFilter} />
        <p className="text-[10px] text-ink-soft mb-2">
          Os mesmos filtros de busca, distância, ordenação e preferências valem
          para o catálogo e para o OpenStreetMap. Filtros de frete e avaliação
          não se aplicam ao OSM, que não fornece esses dados.
        </p>

        {osmError && !osmLoading && (
          <div
            role="status"
            className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
          >
            {osmError}
          </div>
        )}

        {osmLoading ? (
          <div className="space-y-3 sm:grid sm:grid-cols-2 sm:gap-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} variant="card" className="w-full" />
            ))}
          </div>
        ) : osmFiltered.length > 0 ? (
          <div className="space-y-3">
            <RestaurantMap
              restaurants={osmFiltered}
              center={{ lat, lon }}
              selectedKey={selectedOsmKey}
              onSelect={handleSelectOsm}
            />
            <p className="text-[10px] text-ink-soft">
              Selecione um marcador ou um card para ver os detalhes
              disponíveis.
            </p>
            <div className="space-y-3 sm:grid sm:grid-cols-2 sm:gap-3">
              {osmFiltered.map((restaurant) => (
                <OsmRestaurantCard
                  key={osmKey(restaurant)}
                  restaurant={restaurant}
                  query={query}
                  selected={selectedOsmKey === osmKey(restaurant)}
                  onSelect={handleSelectOsm}
                />
              ))}
            </div>
          </div>
        ) : (
          !osmError && (
            <p className="text-center text-ink-soft text-sm py-4">
              {query.trim()
                ? 'Nenhum restaurante do OpenStreetMap corresponde à busca.'
                : 'Nenhum restaurante do OpenStreetMap encontrado para esta região.'}
            </p>
          )
        )}

        <p className="mt-3 text-[10px] text-ink-soft">
          <a
            href={OSM_COPYRIGHT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
          >
            {OSM_ATTRIBUTION}
          </a>{' '}
          · Dados colaborativos; informações podem estar incompletas.
        </p>
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
