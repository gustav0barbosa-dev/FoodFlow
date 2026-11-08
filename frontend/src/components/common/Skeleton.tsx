import { cn } from '@/lib/utils'

export type SkeletonVariant = 'card' | 'row'

interface SkeletonProps {
  variant?: SkeletonVariant
  className?: string
}

const containerStyles: Record<SkeletonVariant, string> = {
  card: 'bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden',
  row: 'flex gap-3 bg-white rounded-2xl p-3 border border-gray-100 shadow-sm',
}

export function Skeleton({ variant = 'row', className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse', containerStyles[variant], className)}
    >
      {variant === 'card' ? <CardLines /> : <RowLines />}
    </div>
  )
}

function CardLines() {
  return (
    <>
      <div className="h-32 bg-gray-200" />
      <div className="p-3 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
        <div className="h-3 bg-gray-200 rounded w-2/3" />
      </div>
    </>
  )
}

function RowLines() {
  return (
    <>
      <div className="w-20 h-20 rounded-xl bg-gray-200 shrink-0" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-4 bg-gray-200 rounded w-2/3" />
        <div className="h-3 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
    </>
  )
}
