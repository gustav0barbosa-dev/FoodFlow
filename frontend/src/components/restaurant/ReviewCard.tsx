import { Star } from 'lucide-react'
import type { Review } from '@/types'

export function ReviewCard({ review }: { review: Review }) {
  return (
    <div className="py-3 border-b border-gray-100">
      <div className="flex items-center justify-between">
        <span className="font-medium text-ink text-sm">{review.userName}</span>
        <span className="text-xs text-ink-soft">{review.date}</span>
      </div>
      <div className="flex items-center gap-0.5 mt-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            size={12}
            className={i < review.rating ? 'text-star fill-star' : 'text-gray-300'}
          />
        ))}
      </div>
      <p className="text-sm text-ink-soft mt-1">{review.comment}</p>
    </div>
  )
}