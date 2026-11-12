import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronLeft, Star, MapPin, Phone, Bike, Clock, ExternalLink, UtensilsCrossed, CreditCard, Globe } from 'lucide-react'
import { MenuItem } from '@/components/restaurant/MenuItem'
import { ReviewCard } from '@/components/restaurant/ReviewCard'
import { UserReviewForm } from '@/components/restaurant/UserReviewForm'
import { FavoriteButton } from '@/components/restaurant/FavoriteButton'
import { StreetView } from '@/components/restaurant/StreetView'
import { EmptyState } from '@/components/common/EmptyState'
import { Skeleton } from '@/components/common/Skeleton'
import { toast } from 'sonner'
import { useCartStore } from '@/store/cartStore'
import { useEventsStore } from '@/store/eventsStore'
import { useReviewsStore } from '@/store/reviewsStore'
import { useCatalogStore } from '@/store/catalogStore'
import { useCatalog } from '@/hooks/useCatalog'
import { deleteReview, getOsmRestaurant, getRestaurant } from '@/lib/api'
import { buildCatalogIdMap, mapApiRestaurantDetail } from '@/lib/catalog'
import { trackInteraction } from '@/lib/interactions'
import { OSM_ATTRIBUTION, OSM_COPYRIGHT_URL } from '@/lib/osm'
import { API_USER_ID, isUuid } from '@/lib/config'
import { formatBRL } from '@/lib/utils'
import { cn } from '@/lib/utils'
import type { Restaurant } from '@/types'

export function RestaurantDetail() {
  const { id, osmType, osmId } = useParams<{
    id?: string
    osmType?: string
    osmId?: string
  }>()
  const navigate = useNavigate()
  const location = useLocation()
  const isOsmRoute = Boolean(osmType && osmId)
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

  const { restaurants: catalogRestaurants, loaded: catalogLoaded } = useCatalog()
  const catalogIdMap = useMemo(
    () => buildCatalogIdMap(catalogRestaurants),
    [catalogRestaurants]
  )
  const resolvedId = id ? (isUuid(id) ? id : catalogIdMap.get(id)) : undefined
  const catalogRestaurant = useMemo(
    () =>
      catalogRestaurants.find(
        (restaurant) => restaurant.id === (resolvedId ?? id)
      ),
    [catalogRestaurants, resolvedId, id]
  )
  const waitingForCatalog =
    !!id && !isUuid(id) && !resolvedId && !catalogLoaded

  useEffect(() => {
    let active = true

    if (isOsmRoute) {
      const validType =
        osmType === 'node' || osmType === 'way' || osmType === 'relation'
      const numericId = Number(osmId)

      if (!validType || !Number.isInteger(numericId) || numericId <= 0) {
        setDetail(null)
        setDetailLoading(false)
        return () => {
          active = false
        }
      }

      setDetail(null)
      setDetailLoading(true)
      getOsmRestaurant(osmType, numericId)
        .then((apiDetail) => {
          if (active) setDetail(mapApiRestaurantDetail(apiDetail))
        })
        .catch(() => {
          if (active) setDetail(null)
        })
        .finally(() => {
          if (active) setDetailLoading(false)
        })

      return () => {
        active = false
      }
    }

    if (!id) {
      setDetail(null)
      setDetailLoading(false)
      return
    }

    if (waitingForCatalog) {
      setDetailLoading(true)
      return () => {
        active = false
      }
    }

    // ID legado/desconhecido que não existe no catálogo atual.
    if (!resolvedId) {
      setDetail(null)
      setDetailLoading(false)
      return () => {
        active = false
      }
    }

    const cached = useCatalogStore
      .getState()
      .restaurants.find((restaurant) => restaurant.id === resolvedId)

    // Enquanto o catálogo ainda é local, exibe o item mock correspondente.
    if (!isUuid(resolvedId)) {
      setDetail(cached ?? null)
      setDetailLoading(false)
      return () => {
        active = false
      }
    }

    setDetailLoading(true)
    getRestaurant(resolvedId)
      .then((apiDetail) => {
        if (!active) return
        const isRecommended = useCatalogStore
          .getState()
          .recommendedIds.includes(resolvedId)
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
  }, [
    id,
    resolvedId,
    waitingForCatalog,
    refreshToken,
    isOsmRoute,
    osmType,
    osmId,
  ])

  const restaurant = isOsmRoute
    ? detail
    : detail && detail.id === resolvedId
      ? detail
      : catalogRestaurant
  const isOsm = restaurant?.source === 'osm'

  // Sempre deriva a lista de um array estável. O seletor anterior devolvia um
  // novo array a cada render e causava loop infinito no useSyncExternalStore.
  const allUserReviews = useReviewsStore((s) => s.reviews)
  const userReviews = useMemo(
    () =>
      allUserReviews.filter(
        (review) => review.restaurantId === restaurant?.id
      ),
    [allUserReviews, restaurant?.id]
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

  // O OSM não fornece cardápio nem avaliações; a tela mantém o mesmo padrão
  // visual, mas exibe apenas a seção com dados disponíveis.
  const availableTabs: Array<'menu' | 'reviews' | 'about'> = isOsm
    ? ['about']
    : ['menu', 'reviews', 'about']
  const activeTab = availableTabs.includes(tab) ? tab : 'about'

  useEffect(() => {
    if (!restaurant || lastTrackedId.current === restaurant.id) return
    lastTrackedId.current = restaurant.id
    trackEvent('restaurant_opened', {
      restaurantId: restaurant.id,
      restaurantName: restaurant.name,
      category: restaurant.category,
    })

    const recommendationContext = useCatalogStore.getState().recommendationContext
    const context = {
      experimentGroup: recommendationContext?.experimentGroup,
      experimentMode: recommendationContext?.experimentMode,
      experimentVersion: recommendationContext?.experimentVersion,
      recommendationId: recommendationContext?.recommendationId,
      recommendationPosition:
        recommendationContext?.positions[restaurant.id],
      modelVersion: recommendationContext?.modelVersion,
    }

    // O clique no card/marcador chega via state da navegação. Só é possível
    // registrar depois que o restaurante do OSM foi persistido e recebeu UUID.
    const navigationState = location.state as
      | { interaction?: string }
      | null
    if (navigationState?.interaction === 'CLICK') {
      trackInteraction(restaurant.id, 'CLICK', context)
    }
    // VIEW_DETAILS representa a abertura da tela de detalhes (sinal mais forte
    // que a impressão); VIEW é mantido por compatibilidade com o histórico.
    trackInteraction(restaurant.id, 'VIEW_DETAILS', context)
    trackInteraction(restaurant.id, 'VIEW', context)
  }, [restaurant, trackEvent, location.state])

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
        {restaurant.image ? (
          <img src={restaurant.image} alt={restaurant.name} className="w-full h-52 object-cover" />
        ) : (
          <div
            className="w-full h-40 bg-gradient-to-br from-primary/10 via-surface-muted to-white flex items-center justify-center"
            aria-hidden="true"
          >
            <MapPin size={40} className="text-primary/50" />
          </div>
        )}
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
        <p className="text-sm text-ink-soft">
          {[restaurant.category, isOsm ? restaurant.cuisine : null]
            .filter((value): value is string => Boolean(value))
            .join(' · ')}
        </p>
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
          {!isOsm && (
            <div className="flex items-center gap-2">
              <Star size={14} className="text-star fill-star" />
              {restaurant.rating} ({restaurant.reviewCount} avaliações)
            </div>
          )}
          {restaurant.address && (
            <div className="flex items-start gap-2">
              <MapPin size={14} className="mt-0.5 shrink-0" />
              <div className="min-w-0">
                <span>{restaurant.address}</span>
                <a
                  href={
                    isOsm
                      ? restaurant.osmUrl ??
                        (restaurant.latitude != null &&
                        restaurant.longitude != null
                          ? `https://www.openstreetmap.org/?mlat=${restaurant.latitude}&mlon=${restaurant.longitude}#map=17/${restaurant.latitude}/${restaurant.longitude}`
                          : undefined)
                      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(restaurant.address)}`
                  }
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-1 flex items-center gap-1 text-primary text-xs font-medium underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  aria-label={`Abrir ${restaurant.name} no mapa`}
                >
                  <ExternalLink size={12} />
                  {isOsm ? 'Ver no OpenStreetMap' : 'Abrir no mapa'}
                </a>
              </div>
            </div>
          )}
          {isOsm &&
            restaurant.latitude != null &&
            restaurant.longitude != null && (
              <div className="flex items-center gap-2 text-xs text-ink-soft">
                <MapPin size={14} className="shrink-0" />
                {restaurant.latitude.toFixed(5)}, {restaurant.longitude.toFixed(5)}
              </div>
            )}
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
          {isOsm && restaurant.website && (
            <div className="flex items-center gap-2">
              <Globe size={14} className="shrink-0" />
              <a
                href={restaurant.website}
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary underline rounded truncate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {restaurant.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            </div>
          )}
          {!isOsm && (
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
          )}
          {isOsm && (
            <p className="pt-1 text-[10px] text-ink-soft">
              <a
                href={OSM_COPYRIGHT_URL}
                target="_blank"
                rel="noreferrer noopener"
                className="underline rounded hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {OSM_ATTRIBUTION}
              </a>
            </p>
          )}
        </div>

        {restaurant.latitude != null && restaurant.longitude != null && (
          <StreetView
            latitude={restaurant.latitude}
            longitude={restaurant.longitude}
            name={restaurant.name}
          />
        )}

        {/* Tabs */}
        <div
          role="group"
          aria-label="Seções do restaurante"
          className="flex gap-1 mt-4 border-b border-gray-100"
        >
          {availableTabs.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={activeTab === t}
              onClick={() => setTab(t)}
              className={`px-3 py-2 text-sm font-medium rounded-t focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                activeTab === t ? 'text-primary border-b-2 border-primary' : 'text-ink-soft'
              }`}
            >
              {t === 'menu' ? 'Cardápio' : t === 'reviews' ? 'Avaliações' : 'Sobre'}
            </button>
          ))}
        </div>

        <div className="mt-3">
          {activeTab === 'menu' &&
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
          {activeTab === 'reviews' && (
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
          {activeTab === 'about' && (
            <section className="space-y-3">
              {isOsm ? (
                <>
                  {restaurant.address && (
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin size={14} className="text-primary" />
                        <span className="font-medium text-ink">Endereço</span>
                      </div>
                      <p className="text-sm text-ink">{restaurant.address}</p>
                    </div>
                  )}

                  {restaurant.cuisine && (
                    <div>
                      <div className="flex items-center gap-2">
                        <UtensilsCrossed size={14} className="text-primary" />
                        <span className="font-medium text-ink">Cozinha</span>
                      </div>
                      <p className="text-sm text-ink">{restaurant.cuisine}</p>
                    </div>
                  )}

                  {(restaurant.openingHours ?? restaurant.hours) && (
                    <div>
                      <div className="flex items-center gap-2">
                        <Clock size={14} className="text-primary" />
                        <span className="font-medium text-ink">
                          Horário de funcionamento
                        </span>
                      </div>
                      <p className="text-sm text-ink">
                        {restaurant.openingHours ?? restaurant.hours}
                      </p>
                    </div>
                  )}

                  {restaurant.website && (
                    <div>
                      <div className="flex items-center gap-2">
                        <Globe size={14} className="text-primary" />
                        <span className="font-medium text-ink">Site</span>
                      </div>
                      <a
                        href={restaurant.website}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-sm text-primary underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      >
                        {restaurant.website}
                      </a>
                    </div>
                  )}

                  {restaurant.osmUrl && (
                    <a
                      href={restaurant.osmUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-primary underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      <ExternalLink size={14} />
                      Ver no OpenStreetMap
                    </a>
                  )}

                  {!restaurant.address &&
                    !restaurant.cuisine &&
                    !restaurant.openingHours &&
                    !restaurant.website && (
                      <p className="text-sm text-ink-soft">
                        O OpenStreetMap não possui informações adicionais
                        cadastradas para este estabelecimento.
                      </p>
                    )}

                  <p className="text-[10px] text-ink-soft">
                    Dados colaborativos do OpenStreetMap; informações podem
                    estar incompletas.
                  </p>
                </>
              ) : (
                <>
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
                </>
              )}
            </section>
          )}
        </div>
      </div>

      {/* Rodapé: o OSM não tem cardápio nem pedido no FoodFlow. */}
      {!isOsm && (
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
      )}
    </div>
  )
}
