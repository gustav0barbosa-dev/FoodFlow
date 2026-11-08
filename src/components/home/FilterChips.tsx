import { cn } from '@/lib/utils'

const FILTERS = ['Todos', 'Vegano', 'Promoções', 'Frete grátis', 'Mais bem avaliados']

export function FilterChips({
  active,
  onChange,
}: {
  active: string
  onChange: (value: string) => void
}) {
  return (
    <div
      role="group"
      aria-label="Filtrar restaurantes"
      className="flex gap-2 overflow-x-auto no-scrollbar py-2"
    >
      {FILTERS.map((f) => (
        <button
          key={f}
          type="button"
          onClick={() => onChange(f)}
          aria-pressed={active === f}
          className={cn(
            'whitespace-nowrap rounded-full border px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
            active === f
              ? 'bg-primary text-white border-primary'
              : 'bg-white text-ink border-gray-200 hover:bg-surface-muted'
          )}
        >
          {f}
        </button>
      ))}
    </div>
  )
}
