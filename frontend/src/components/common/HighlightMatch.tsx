import { splitHighlight } from '@/lib/search'
import { cn } from '@/lib/utils'

interface HighlightMatchProps {
  text: string
  query: string
  className?: string
}

export function HighlightMatch({ text, query, className }: HighlightMatchProps) {
  return (
    <span className={cn(className)}>
      {splitHighlight(text, query).map((part, index) =>
        part.match ? (
          <mark
            key={`${part.text}-${index}`}
            className="rounded-sm bg-primary/15 px-0.5 text-primary-dark"
          >
            {part.text}
          </mark>
        ) : (
          <span key={`${part.text}-${index}`}>{part.text}</span>
        )
      )}
    </span>
  )
}
