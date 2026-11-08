import { beforeEach, describe, expect, it } from 'vitest'
import { useReviewsStore } from '@/store/reviewsStore'
import type { UserReview } from '@/store/reviewsStore'

describe('reviewsStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useReviewsStore.setState({ reviews: [] })
  })

  it('inicia sem avaliações', () => {
    expect(useReviewsStore.getState().reviews).toEqual([])
  })

  it('adiciona uma avaliação vinculada ao restaurante', () => {
    useReviewsStore.getState().addReview('r1', 5, 'Ótima comida!')

    const reviews = useReviewsStore.getState().getReviewsForRestaurant('r1')
    expect(reviews).toHaveLength(1)
    expect(reviews[0].rating).toBe(5)
    expect(reviews[0].comment).toBe('Ótima comida!')
    expect(reviews[0].userName).toBeDefined()
  })

  it('não retorna avaliações de outro restaurante', () => {
    useReviewsStore.getState().addReview('r1', 4, 'Bom')

    expect(useReviewsStore.getState().getReviewsForRestaurant('r2')).toEqual([])
  })

  it('indica se o usuário já avaliou o restaurante', () => {
    expect(useReviewsStore.getState().hasReviewed('r1')).toBe(false)

    useReviewsStore.getState().addReview('r1', 3, 'Regular')

    expect(useReviewsStore.getState().hasReviewed('r1')).toBe(true)
  })

  it('persiste as avaliações em localStorage', () => {
    useReviewsStore.getState().addReview('r1', 5, 'Excelente')

    const stored = localStorage.getItem('foodflow-reviews')
    expect(stored).toContain('Excelente')
  })
})
