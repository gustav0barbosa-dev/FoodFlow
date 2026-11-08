import { useParams, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { ChevronLeft, Star, MapPin, Phone, Bike, Clock } from 'lucide-react'
import { restaurants } from '@/data/mockData'
import { MenuItem } from '@/components/restaurant/MenuItem'
import { ReviewCard } from '@/components/restaurant/ReviewCard'
import { useCartStore } from '@/store/cartStore'
import { formatBRL } from '@/lib/utils'

export function RestaurantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'menu' | 'reviews' | 'about'>('menu')
  const total = useCartStore((s) => s.total())
  const count = useCartStore((s) => s.count())

  const restaurant = restaurants.find((r) => r.id === id)
  if (!restaurant) {
    return <div className="p-6 text-center">Restaurante não encontrado</div>
  }

  return (
    <div className="h-full overflow-y-auto pb-24 bg-white">
      {/* Hero */}
      <div className="relative">
        <img src={restaurant.image} alt={restaurant.name} className="w-full h-52 object-cover" />
        <button
          onClick={() => navigate(-1)}
          className="absolute top-3 left-3 w-9 h-9 rounded-full bg-white flex items-center justify-center shadow"
          aria-label="Voltar"
        >
          <ChevronLeft size={20} />
        </button>
      </div>

      <div className="p-4">
        <h1 className="font-display font-bold text-xl text-ink">{restaurant.name}</h1>
        <p className="text-sm text-ink-soft">{restaurant.category}</p>
        {restaurant.isRecommended && (
          <span className="inline-block mt-2 bg-purple-100 text-purple-700 text-xs font-semibold px-2 py-1 rounded-full">
            ✨ Recomendado para você
          </span>
        )}

        {/* Info card */}
        <div className="mt-4 p-3 bg-surface-muted rounded-2xl space-y-1.5 text-sm text-ink">
          <div className="flex items-center gap-2">
            <Star size={14} className="text-star fill-star" />
            {restaurant.rating} ({restaurant.reviewCount} avaliações)
          </div>
          <div className="flex items-center gap-2">
            <MapPin size={14} /> {restaurant.address}
          </div>
          <div className="flex items-center gap-2">
            <Phone size={14} />
            <a href={`tel:${restaurant.phone}`} className="text-primary underline">
              {restaurant.phone}
            </a>
          </div>
          <div className="flex items-center gap-3 text-ink-soft text-xs pt-1">
            <span className="flex items-center gap-1">
              <Bike size={12} />
              {restaurant.deliveryFee === 0 ? 'Grátis' : formatBRL(restaurant.deliveryFee)}
            </span>
            <span className="flex items-center gap-1">
              <Clock size={12} />
              {restaurant.deliveryTimeMin}-{restaurant.deliveryTimeMax} min
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 border-b border-gray-100">
          {(['menu', 'reviews', 'about'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-sm font-medium ${
                tab === t ? 'text-primary border-b-2 border-primary' : 'text-ink-soft'
              }`}
            >
              {t === 'menu' ? 'Cardápio' : t === 'reviews' ? 'Avaliações' : 'Sobre'}
            </button>
          ))}
        </div>

        <div className="mt-3">
          {tab === 'menu' &&
            restaurant.menu.map((item) => (
              <MenuItem
                key={item.id}
                item={item}
                restaurantId={restaurant.id}
                restaurantName={restaurant.name}
              />
            ))}
          {tab === 'reviews' &&
            restaurant.reviews.map((r) => <ReviewCard key={r.id} review={r} />)}
          {tab === 'about' && (
            <p className="text-sm text-ink-soft py-3">
              {/* TODO: horários, formas de pagamento */}
              Informações do restaurante em breve.
            </p>
          )}
        </div>
      </div>

      {/* Rodapé */}
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] p-3 bg-white border-t border-gray-100">
        <button
          onClick={() => navigate('/sacola')}
          disabled={count === 0}
          className="w-full bg-primary text-white rounded-2xl py-3 font-semibold disabled:opacity-50 hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          Ver sacola · {formatBRL(total)}
        </button>
      </div>
    </div>
  )
}