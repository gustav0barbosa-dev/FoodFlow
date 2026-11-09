import { ChevronLeft, Heart } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useCatalog } from '@/hooks/useCatalog'
import { useFavoritesStore } from '@/store/favoritesStore'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'
import { EmptyState } from '@/components/common/EmptyState'

export function Favorites() {
  const navigate = useNavigate()
  const { restaurants } = useCatalog()
  const favoriteIds = useFavoritesStore((s) => s.favoriteIds)
  const favorites = restaurants.filter((restaurant) =>
    favoriteIds.includes(restaurant.id)
  )

  return (
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 py-4 border-b border-gray-100 flex items-center gap-2">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="w-9 h-9 rounded-full flex items-center justify-center text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          aria-label="Voltar"
        >
          <ChevronLeft size={20} />
        </button>
        <div>
          <h1 className="font-display font-bold text-lg text-ink leading-tight">Favoritos</h1>
          <p className="text-xs text-ink-soft">
            {favorites.length === 0
              ? 'Nenhum salvo'
              : `${favorites.length} ${
                  favorites.length === 1 ? 'restaurante salvo' : 'restaurantes salvos'
                }`}
          </p>
        </div>
      </header>

      {favorites.length === 0 ? (
        <EmptyState
          icon={Heart}
          title="Nenhum favorito ainda"
          description="Toque no coração dos restaurantes que você gosta para encontrá-los aqui."
          actionLabel="Explorar restaurantes"
          onAction={() => navigate('/home')}
          className="pt-24"
        />
      ) : (
        <div className="p-4 space-y-3 sm:max-w-[700px] sm:mx-auto">
          {favorites.map((restaurant) => (
            <RestaurantCompactCard
              key={restaurant.id}
              restaurant={restaurant}
              source="favorites"
            />
          ))}
        </div>
      )}
    </div>
  )
}
