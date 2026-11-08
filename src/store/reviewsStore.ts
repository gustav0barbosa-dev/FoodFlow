import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { currentUser } from '@/data/mockData'
import type { Review } from '@/types'

export interface UserReview extends Review {
  restaurantId: string
}

interface ReviewsState {
  reviews: UserReview[]
  addReview: (restaurantId: string, rating: number, comment: string) => void
  getReviewsForRestaurant: (restaurantId: string) => Review[]
  hasReviewed: (restaurantId: string) => boolean
}

export const useReviewsStore = create<ReviewsState>()(
  persist(
    (set, get) => ({
      reviews: [],

      addReview: (restaurantId, rating, comment) => {
        const review: UserReview = {
          id: `u${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          userName: currentUser.name,
          rating,
          date: new Date().toISOString(),
          comment,
          restaurantId,
        }

        set({ reviews: [review, ...get().reviews] })
      },

      getReviewsForRestaurant: (restaurantId) =>
        get().reviews.filter((r) => r.restaurantId === restaurantId),

      hasReviewed: (restaurantId) =>
        get().reviews.some((r) => r.restaurantId === restaurantId),
    }),
    {
      name: 'foodflow-reviews',
      partialize: (state) => ({ reviews: state.reviews }),
    }
  )
)
