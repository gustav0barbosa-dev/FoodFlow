import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  headingLevel?: 'h1' | 'h2'
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  headingLevel = 'h2',
  className,
}: EmptyStateProps) {
  const Heading = headingLevel

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center px-8 text-center',
        className
      )}
    >
      <div className="w-20 h-20 rounded-full bg-white text-ink-soft flex items-center justify-center shadow-sm">
        <Icon size={32} aria-hidden="true" />
      </div>
      <Heading className="mt-4 font-display text-lg font-bold text-ink">
        {title}
      </Heading>
      {description && <p className="mt-1 text-sm text-ink-soft">{description}</p>}
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-6 bg-primary text-white rounded-2xl px-6 py-3 font-semibold hover:bg-primary-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
