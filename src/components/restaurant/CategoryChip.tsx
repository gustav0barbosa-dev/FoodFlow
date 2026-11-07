export function CategoryChip({ emoji, name }: { emoji: string; name: string }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="w-16 h-16 rounded-2xl bg-surface-muted flex items-center justify-center text-2xl">
        {emoji}
      </div>
      <span className="text-xs text-ink">{name}</span>
    </div>
  )
}