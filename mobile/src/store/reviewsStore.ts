import { create } from 'zustand'

export interface ReviewsState {
  reviews: any[]
  addReview: (restaurantId: string, rating: number, comment: string) => void
  saveReview: (review: any) => void
  updateReview: (restaurantId: string, rating: number, comment: string) => void
  removeReview: (restaurantId: string) => void
  getReviewsForRestaurant: (restaurantId: string) => any[]
  getUserReview: (restaurantId: string) => any | undefined
  hasReviewed: (restaurantId: string) => boolean
}

export const useReviewsStore = create<ReviewsState>((set, get) => ({
  reviews: [],

  addReview: (restaurantId, rating, comment) => {
    const review = {
      id: `u${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      userName: 'Ana Souza',
      rating,
      date: new Date().toISOString(),
      comment,
      restaurantId,
    }

    set({ reviews: [review, ...get().reviews] })
  },

  saveReview: (review) => {
    const others = get().reviews.filter(
      (item) => item.restaurantId !== review.restaurantId
    )
    set({ reviews: [review, ...others] })
  },

  updateReview: (restaurantId, rating, comment) => {
    const review = get().reviews.find((r) => r.restaurantId === restaurantId)
    if (!review) return

    set({
      reviews: get().reviews.map((r) =>
        r.restaurantId === restaurantId
          ? { ...r, rating, comment, date: new Date().toISOString() }
          : r
      ),
    })
  },

  removeReview: (restaurantId) => {
    set({ reviews: get().reviews.filter((r) => r.restaurantId !== restaurantId) })
  },

  getReviewsForRestaurant: (restaurantId) =>
    get().reviews.filter((r) => r.restaurantId === restaurantId),

  getUserReview: (restaurantId) =>
    get().reviews.find((r) => r.restaurantId === restaurantId),

  hasReviewed: (restaurantId) =>
    get().reviews.some((r) => r.restaurantId === restaurantId),
}))
