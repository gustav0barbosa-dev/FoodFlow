import type { AddressFields } from '@/lib/address'
import { formatCep } from '@/lib/validation'

/**
 * Reverse geocoding via Nominatim/OpenStreetMap.
 *
 * O backend atual não possui rota de geocoding. Para produção, o ideal é
 * mover esta chamada para o backend (assim é possível aplicar cache, rate
 * limit e um User-Agent próprio). O Nominatim exige uso moderado.
 */

export interface ReverseGeocodeResult {
  address: Partial<AddressFields>
  label: string | null
}

interface NominatimResponse {
  display_name?: string
  address?: Record<string, unknown>
}

const REQUEST_TIMEOUT_MS = 9000

function read(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function readState(address: Record<string, unknown>) {
  const candidates = [
    address.state_code,
    address['ISO3166-2-lvl4'],
    address.state,
  ]

  for (const candidate of candidates) {
    const value = read(candidate)
    if (!value) continue

    const isoMatch = value.match(/([A-Za-z]{2})$/)
    if (isoMatch) return isoMatch[1].toUpperCase()
  }

  return ''
}

export async function reverseGeocode(
  lat: number,
  lon: number
): Promise<ReverseGeocodeResult | null> {
  if (typeof fetch !== 'function') return null

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  const url = new URL('https://nominatim.openstreetmap.org/reverse')
  url.searchParams.set('format', 'jsonv2')
  url.searchParams.set('lat', String(lat))
  url.searchParams.set('lon', String(lon))
  url.searchParams.set('addressdetails', '1')
  url.searchParams.set('accept-language', 'pt-BR')

  try {
    const response = await fetch(url.toString(), {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })

    if (!response.ok) return null

    const data = (await response.json()) as NominatimResponse
    const address = data.address ?? {}

    const street = read(
      address.road ?? address.pedestrian ?? address.footway ?? address.path
    )
    const neighborhood = read(
      address.suburb ??
        address.neighbourhood ??
        address.city_district ??
        address.quarter
    )
    const city = read(
      address.city ?? address.town ?? address.village ?? address.municipality
    )
    const state = readState(address)
    const cep = read(address.postcode)
    const number = read(address.house_number)

    const partial: Partial<AddressFields> = {}
    if (street) partial.street = street
    if (number) partial.number = number
    if (neighborhood) partial.neighborhood = neighborhood
    if (city) partial.city = city
    if (state) partial.state = state
    if (cep) partial.cep = formatCep(cep)

    const label = read(data.display_name) || null

    if (Object.keys(partial).length === 0 && !label) return null

    return { address: partial, label }
  } catch {
    return null
  } finally {
    clearTimeout(timeout)
  }
}
