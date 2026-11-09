import { Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { currentUser } from '@/data/mockData'
import { createReview, updateReview } from '@/lib/api'
import { mapApiReview } from '@/lib/catalog'
import { API_USER_ID, isUuid } from '@/lib/config'
import { useEventsStore } from '@/store/eventsStore'
import { useReviewsStore, type UserReview } from '@/store/reviewsStore'
import { cn } from '@/lib/utils'

interface UserReviewFormProps {
  restaurantId: string
  reviewId?: string
  onReviewSubmitted: () => void
  initialRating?: number
  initialComment?: string
}

export function UserReviewForm({
  restaurantId,
  reviewId,
  onReviewSubmitted,
  initialRating,
  initialComment,
}: UserReviewFormProps) {
  const [rating, setRating] = useState(initialRating ?? 0)
  const [comment, setComment] = useState(initialComment ?? '')
  const [isEditing, setIsEditing] = useState(!!(initialRating ?? initialComment))
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const addReview = useReviewsStore((s) => s.addReview)
  const updateReviewLocal = useReviewsStore((s) => s.updateReview)
  const saveReview = useReviewsStore((s) => s.saveReview)

  useEffect(() => {
    if (initialRating !== undefined) setRating(initialRating)
    if (initialComment !== undefined) setComment(initialComment)
    setIsEditing(!!(initialRating ?? initialComment))
  }, [initialRating, initialComment])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()

    if (rating === 0) {
      toast.error('Selecione uma avaliação de 1 a 5 estrelas')
      return
    }

    const editing = isEditing && !!reviewId
    const localReview: UserReview = {
      id:
        editing && reviewId
          ? reviewId
          : `u${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      userName: currentUser.name,
      rating,
      date: new Date().toISOString(),
      comment,
      restaurantId,
    }

    if (editing) {
      updateReviewLocal(restaurantId, rating, comment)
      trackEvent('review_submitted', {
        restaurantId,
        rating: String(rating),
        updated: 'true',
      })
      toast.success('Avaliação atualizada com sucesso')
    } else {
      addReview(restaurantId, rating, comment)
      trackEvent('review_submitted', {
        restaurantId,
        rating: String(rating),
      })
      toast.success('Avaliação enviada com sucesso')
    }

    // Mantém a avaliação otimista e sincroniza com a API quando disponível.
    saveReview(localReview)

    if (isUuid(restaurantId) && isUuid(API_USER_ID)) {
      const request = editing && reviewId && isUuid(reviewId)
        ? updateReview(reviewId, { userId: API_USER_ID, rating, comment })
        : createReview({
            restaurantId,
            userId: API_USER_ID,
            rating,
            comment,
          }, `review-${restaurantId}-${Date.now()}`)

      void request
        .then((review) => {
          saveReview({ ...mapApiReview(review), restaurantId })
        })
        .catch(() => {
          // Sem API, a avaliação local continua disponível.
        })
    }

    onReviewSubmitted()
    setRating(0)
    setComment('')
    setIsEditing(false)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3 bg-white p-4 rounded-2xl border border-gray-100"
    >
      <div>
        <label className="text-xs text-ink-soft block mb-1">
          Sua avaliação
        </label>
        <div
          role="radiogroup"
          aria-label="Avaliar de 1 a 5 estrelas"
          className="flex gap-1"
        >
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              onClick={() => setRating(star)}
              aria-label={`Avaliar com ${star} estrela${star !== 1 ? 's' : ''}`}
              aria-pressed={rating >= star}
              className={cn(
                'w-6 h-6 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                rating >= star
                  ? 'text-star fill-star'
                  : 'text-gray-300 hover:text-star'
              )}
            >
              <Star size={16} />
            </button>
          ))}
        </div>
        {rating === 0 && (
          <p className="text-[11px] text-ink-soft mt-1">Selecione as estrelas</p>
        )}
      </div>

      <div>
        <label htmlFor="review-comment" className="text-xs text-ink-soft block mb-1">
          Comentário
        </label>
        <textarea
          id="review-comment"
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Conte o que achou do restaurante..."
          className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          rows={3}
        />
      </div>

      <button
        type="submit"
        disabled={rating === 0 || comment.trim().length === 0}
        className="w-full bg-primary text-white rounded-xl py-2.5 font-semibold disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        {isEditing ? 'Atualizar avaliação' : 'Enviar avaliação'}
      </button>
    </form>
  )
}
