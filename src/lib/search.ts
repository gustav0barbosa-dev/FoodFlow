import type { MenuItem, Restaurant } from '@/types'

export interface HighlightPart {
  text: string
  match: boolean
}

interface SearchableText {
  normalized: string
  /** Maps each normalized character back to its index in the original text. */
  indexes: number[]
}

function buildSearchable(value: string): SearchableText {
  const chars: string[] = []
  const indexes: number[] = []

  for (let index = 0; index < value.length; index += 1) {
    const normalized = value[index]
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()

    for (const char of normalized) {
      chars.push(char)
      indexes.push(index)
    }
  }

  return { normalized: chars.join(''), indexes }
}

function normalize(value: string) {
  return buildSearchable(value).normalized
}

function includesTerm(value: string, term: string) {
  return normalize(value).includes(term)
}

export function getMatchingMenuItems(
  restaurant: Restaurant,
  query: string
): MenuItem[] {
  const term = normalize(query.trim())
  if (!term) return []

  return restaurant.menu.filter((item) => includesTerm(item.name, term))
}

export function filterRestaurants(restaurants: Restaurant[], query: string) {
  const term = normalize(query.trim())
  if (!term) return restaurants

  return restaurants.filter(
    (restaurant) =>
      includesTerm(restaurant.name, term) ||
      includesTerm(restaurant.category, term) ||
      restaurant.menu.some((item) => includesTerm(item.name, term))
  )
}

export function splitHighlight(text: string, query: string): HighlightPart[] {
  const term = normalize(query.trim())
  if (!term) return [{ text, match: false }]

  const searchable = buildSearchable(text)
  const parts: HighlightPart[] = []
  let cursor = 0
  let found = searchable.normalized.indexOf(term)

  while (found !== -1) {
    const start = searchable.indexes[found]
    const end = searchable.indexes[found + term.length - 1] + 1

    if (start > cursor) {
      parts.push({ text: text.slice(cursor, start), match: false })
    }
    parts.push({ text: text.slice(start, end), match: true })
    cursor = end
    found = searchable.normalized.indexOf(term, found + term.length)
  }

  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor), match: false })
  }

  return parts
}
