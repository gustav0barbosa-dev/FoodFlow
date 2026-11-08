import { ChevronLeft, Heart } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { restaurants } from '@/data/mockData'
import { useFavoritesStore } from '@/store/favoritesStore'
import { RestaurantCompactCard } from '@/components/restaurant/RestaurantCompactCard'

export function Favorites() {
  const navigate = useNavigate()
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
        <div className="flex flex-col items-center justify-center px-8 pt-24 text-center">
          <div className="w-20 h-20 rounded-full bg-white text-ink-soft flex items-center justify-center shadow-sm">
            <Heart size={32} />
          </div>
          <h2 className="mt-4 font-display text-lg font-bold text-ink">
            Nenhum favorito ainda
          </h2>
          <p className="mt-1 text-sm text-ink-soft">
            Toque no coração dos restaurantes que você gosta para encontrá-los aqui.
          </p>
          <button
            type="button"
            onClick={() => navigate('/home')}
            className="mt-6 bg-primary text-white rounded-2xl px-6 py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            Explorar restaurantes
          </button>
        </div>
      ) : (
        <div className="p-4 space-y-3">
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
