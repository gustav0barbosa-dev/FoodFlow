import { Search } from 'lucide-react'

export function SearchBar({
  value,
  onChange,
  placeholder = 'Buscar restaurantes...',
  autoFocus = false,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  autoFocus?: boolean
}) {
  return (
    <div className="flex items-center gap-2 bg-surface-muted rounded-2xl px-3 py-2.5">
      <Search size={18} className="text-ink-soft" />
      <input
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-transparent outline-none text-sm placeholder:text-ink-soft"
      />
    </div>
  )
}