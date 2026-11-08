import { useEffect, useRef } from 'react'
import { useEventsStore } from '@/store/eventsStore'

const DEBOUNCE_MS = 400
const MIN_QUERY_LENGTH = 2

export function useSearchTracking({
  query,
  results,
  source,
  enabled = true,
}: {
  query: string
  results: number
  source: string
  enabled?: boolean
}) {
  const trackEvent = useEventsStore((s) => s.trackEvent)
  const lastTracked = useRef('')

  useEffect(() => {
    if (!enabled) return

    const term = query.trim()
    if (term.length < MIN_QUERY_LENGTH) return

    const timeout = setTimeout(() => {
      if (term === lastTracked.current) return
      lastTracked.current = term
      trackEvent('search_performed', { query: term, source, results })
    }, DEBOUNCE_MS)

    return () => clearTimeout(timeout)
  }, [query, results, source, enabled, trackEvent])
}
