import { useParams, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, Star, MapPin, Phone, Bike, Clock, ExternalLink, UtensilsCrossed, CreditCard } from 'lucide-react'
import { MenuItem } from '@/components/restaurant/MenuItem'
import { ReviewCard } from '@/components/restaurant/ReviewCard'
import { UserReviewForm } from '@/components/restaurant/UserReviewForm'
import { FavoriteButton } from '@/components/restaurant/FavoriteButton'
import { EmptyState } from '@/components/common/EmptyState'
import { Skeleton } from '@/components/common/Skeleton'
import { toast } from 'sonner'
import { useCartStore } from '@/store/cartStore'
import { useEventsStore } from '@/store/eventsStore'
import { useReviewsStore } from '@/store/reviewsStore'
import { useCatalogStore } from '@/store/catalogStore'
import { deleteReview, getRestaurant } from '@/lib/api'
import { mapApiRestaurantDetail } from '@/lib/catalog'
import { API_USER_ID, isUuid } from '@/lib/config'
import { formatBRL } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Restaurant } from '@/types'

export function RestaurantDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<'menu' | 'reviews' | 'about'>('menu')
  const total = useCartStore((s) => s.total())
  const count = useCartStore((s) => s.count())
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const lastTrackedId = useRef<string | null>(null)
  const removeReview = useReviewsStore((s) => s.removeReview)
  const [editingReview, setEditingReview] = useState(false)
  const [detail, setDetail] = useState<Restaurant | null>(null)
  const [detailLoading, setDetailLoading] = useState(true)
  const [refreshToken, setRefreshToken] = useState(0)

  const catalogRestaurants = useCatalogStore((s) => s.restaurants)
  const catalogRestaurant = catalogRestaurants.find((r) => r.id === id)

  useEffect(() => {
    if (!id) return

    let active = true
    const cached = useCatalogStore
      .getState()
      .restaurants.find((restaurant) => restaurant.id === id)

    if (!isUuid(id)) {
      setDetail(cached ?? null)
      setDetailLoading(false)
      return
    }

    setDetailLoading(true)
    getRestaurant(id)
      .then((apiDetail) => {
        if (!active) return
        const isRecommended = useCatalogStore
          .getState()
          .recommendedIds.includes(id)
        setDetail(mapApiRestaurantDetail(apiDetail, isRecommended))
      })
      .catch(() => {
        if (active) setDetail(cached ?? null)
      })
      .finally(() => {
        if (active) setDetailLoading(false)
      })

    return () => {
      active = false
    }
  }, [id, refreshToken, catalogRestaurants])

  const restaurant = detail ?? catalogRestaurant

  const userReviews = useReviewsStore((s) =>
    s.getReviewsForRestaurant(restaurant?.id ?? '')
  )
  const apiReviews = restaurant?.reviews ?? []
  const apiUserReview = apiReviews.find(
    (review) => review.userId === API_USER_ID
  )
  const userReview = userReviews[0] ?? apiUserReview
  const hasReviewed = !!userReview

  const localOnlyReviews = userReviews.filter(
    (review) => !apiReviews.some((apiReview) => apiReview.id === review.id)
  )
  const reviews = [...localOnlyReviews, ...apiReviews]

  useEffect(() => {
    if (!restaurant || lastTrackedId.current === restaurant.id) return
    lastTrackedId.current = restaurant.id
    trackEvent('restaurant_opened', {
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      category: restaurant.category,
    })
  }, [restaurant, trackEvent])

  const handleRemoveReview = () => {
    if (!restaurant || !userReview) return

    const reviewId = userReview.id
    removeReview(restaurant.id)
    setEditingReview(false)
    toast.success('Avaliação removida')

    if (isUuid(reviewId) && isUuid(API_USER_ID)) {
      void deleteReview(reviewId, API_USER_ID)
        .then(() => setRefreshToken((current) => current + 1))
        .catch(() => {
          // Sem API, a remoção local permanece válida.
        })
    }
  }

  if (!restaurant && detailLoading) {
    return (
      <div className="h-full bg-white p-4">
        <Skeleton variant="card" />
      </div>
    )
  }

  if (!restaurant) {
    return (
      <EmptyState
        icon={UtensilsCrossed}
        headingLevel="h1"
        title="Restaurante não encontrado"
        description="Ele pode ter saído do ar ou o link está incorreto."
        actionLabel="Voltar"
        onAction={() => navigate(-1)}
        className="h-full bg-white"
      />
    )
  }

  return (
    <div
      className={cn(
        'h-full overflow-y-auto pb-24 bg-white',
        // Tablet/Desktop: não esticar conteúdo em telas largas.
        'sm:max-w-[700px] sm:mx-auto'
      )}
    >
      {/* Hero */}
      <div className="relative">
        <img src={restaurant.image} alt={restaurant.name} className="w-full h-52 object-cover" />
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="absolute top-3 left-3 w-9 h-9 rounded-full bg-white flex items-center justify-center shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          aria-label="Voltar"
        >
          <ChevronLeft size={20} />
        </button>
        <FavoriteButton restaurant={restaurant} className="absolute top-3 right-3" />
      </div>

      <div className="p-4">
        <h1 className="font-display font-bold text-xl text-ink">{restaurant.name}</h1>
        <p className="text-sm text-ink-soft">{restaurant.category}</p>
        {restaurant.dietaryTags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {restaurant.dietaryTags.map((tag) => (
              <span
                key={tag}
                className="text-[11px] font-medium px-2 py-1 rounded-full bg-green-50 text-green-700"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
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
          <div className="flex items-start gap-2">
            <MapPin size={14} className="mt-0.5 shrink-0" />
            <div className="min-w-0">
              <span>{restaurant.address}</span>
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(restaurant.address)}`}
                target="_blank"
                rel="noreferrer noopener"
                className="mt-1 flex items-center gap-1 text-primary text-xs font-medium underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                aria-label={`Abrir ${restaurant.name} no mapa`}
              >
                <ExternalLink size={12} />
                Abrir no mapa
              </a>
            </div>
          </div>
          {restaurant.phone && (
            <div className="flex items-center gap-2">
              <Phone size={14} />
              <a
                href={`tel:${restaurant.phone}`}
                className="text-primary underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {restaurant.phone}
              </a>
            </div>
          )}
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
        <div
          role="group"
          aria-label="Seções do restaurante"
          className="flex gap-1 mt-4 border-b border-gray-100"
        >
          {(['menu', 'reviews', 'about'] as const).map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={tab === t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-sm font-medium rounded-t focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                tab === t ? 'text-primary border-b-2 border-primary' : 'text-ink-soft'
              }`}
            >
              {t === 'menu' ? 'Cardápio' : t === 'reviews' ? 'Avaliações' : 'Sobre'}
            </button>
          ))}
        </div>

        <div className="mt-3">
          {tab === 'menu' &&
            (restaurant.menu.length > 0 ? (
              <div
                className={cn(
                  // Mobile: lista vertical.
                  'space-y-2',
                  // Tablet/Desktop: grid de 2 colunas.
                  'sm:grid sm:grid-cols-2 sm:gap-3'
                )}
              >
                {restaurant.menu.map((item) => (
                  <MenuItem
                    key={item.id}
                    item={item}
                    restaurantId={restaurant.id}
                    restaurantName={restaurant.name}
                  />
                ))}
              </div>
            ) : (
              <p className="text-xs text-ink-soft text-center py-4">
                Cardápio indisponível no momento.
              </p>
            ))}
          {tab === 'reviews' && (
            <div className="space-y-4">
              {!hasReviewed && !editingReview && (
                <UserReviewForm
                  restaurantId={restaurant.id}
                  onReviewSubmitted={() => setRefreshToken((current) => current + 1)}
                />
              )}
              {hasReviewed && userReview && !editingReview && (
                <section className="bg-green-50 border border-green-100 rounded-xl p-3">
                  <p className="text-xs text-ink-soft mb-1">
                    Sua avaliação
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 text-sm text-ink">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <Star
                          key={star}
                          size={14}
                          className={star <= userReview.rating ? 'text-star fill-star' : 'text-gray-300'}
                        />
                      ))}
                    </div>
                    <p className="text-sm text-ink">{userReview.comment}</p>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => setEditingReview(true)}
                      className="text-xs font-medium text-primary px-2 py-1.5 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={handleRemoveReview}
                      className="text-xs font-medium text-ink-soft px-2 py-1.5 rounded hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      Remover
                    </button>
                  </div>
                </section>
              )}
              {editingReview && userReview && (
                <UserReviewForm
                  restaurantId={restaurant.id}
                  reviewId={userReview.id}
                  initialRating={userReview.rating}
                  initialComment={userReview.comment}
                  onReviewSubmitted={() => {
                    setEditingReview(false)
                    setRefreshToken((current) => current + 1)
                  }}
                />
              )}
              <h3 className="font-semibold text-ink text-sm">
                Avaliações ({reviews.length})
              </h3>
              {reviews.map((review) => (
                <ReviewCard key={review.id} review={review} />
              ))}
              {reviews.length === 0 && (
                <p className="text-xs text-ink-soft text-center py-4">
                  Sem avaliações ainda. Seja o primeiro!
                </p>
              )}
            </div>
          )}
          {tab === 'about' && (
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-primary" />
                <span className="font-medium text-ink">Horário de funcionamento</span>
              </div>
              <p className="text-sm text-ink">{restaurant.hours}</p>

              <div className="flex items-center gap-2">
                <CreditCard size={14} className="text-primary" />
                <span className="font-medium text-ink">Formas de pagamento</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {restaurant.paymentMethods.map((method) => (
                  <span
                    key={method}
                    className="text-xs text-ink border border-gray-200 rounded-full px-3 py-1"
                  >
                    {method}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Rodapé */}
      <div className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] p-3 bg-white border-t border-gray-100">
        <button
          type="button"
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
