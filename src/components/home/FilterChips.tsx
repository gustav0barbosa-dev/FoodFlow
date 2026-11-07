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
    <div className="flex gap-2 overflow-x-auto no-scrollbar py-2">
      {FILTERS.map((f) => (
        <button
          key={f}
          onClick={() => onChange(f)}
          className={cn(
            'whitespace-nowrap rounded-full border px-3 py-1.5 text-sm',
            active === f
              ? 'bg-primary text-white border-primary'
              : 'bg-white text-ink border-gray-200'
          )}
        >
          {f}
        </button>
      ))}
    </div>
  )
}