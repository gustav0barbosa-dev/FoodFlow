import { cn } from '@/lib/utils'

export function CategoryChip({
  emoji,
  name,
  active = false,
  onSelect,
}: {
  emoji: string
  name: string
  active?: boolean
  onSelect?: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className="flex flex-col items-center gap-2 rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <span
        className={cn(
          'w-16 h-16 rounded-2xl flex items-center justify-center text-2xl transition-colors',
          active ? 'bg-primary/10 ring-2 ring-primary' : 'bg-surface-muted'
        )}
      >
        {emoji}
      </span>
      <span className={cn('text-xs', active ? 'text-primary font-semibold' : 'text-ink')}>
        {name}
      </span>
    </button>
  )
}
