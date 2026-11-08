import { AlertCircle, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ErrorStateProps {
  description: string
  title?: string
  actionLabel?: string
  onAction?: () => void
  icon?: LucideIcon
  className?: string
}

export function ErrorState({
  description,
  title = 'Não foi possível carregar',
  actionLabel = 'Tentar novamente',
  onAction,
  icon: Icon = AlertCircle,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center px-8 py-10 text-center',
        className
      )}
    >
      <div className="w-14 h-14 rounded-full bg-white text-primary flex items-center justify-center shadow-sm">
        <Icon size={26} aria-hidden="true" />
      </div>
      <h2 className="mt-3 font-display text-base font-bold text-ink">{title}</h2>
      <p className="mt-1 text-sm text-ink-soft">{description}</p>
      {onAction && (
        <button
          type="button"
          onClick={onAction}
          className="mt-4 text-sm font-medium text-primary px-3 py-1.5 rounded-full border border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
