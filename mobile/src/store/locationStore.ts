import { create } from 'zustand'

export interface LocationState {
  lat: number
  lon: number
  label: string
  setLocation: (location: { lat: number; lon: number; label?: string }) => void
  resetLocation: () => void
}

export const DEFAULT_LOCATION = {
  lat: -23.5325,
  lon: -46.7939,
  label: 'Osasco, SP',
}

export const useLocationStore = create<LocationState>((set) => ({
  ...DEFAULT_LOCATION,

  setLocation: ({ lat, lon, label }) =>
    set({
      lat,
      lon,
      label: label?.trim() || 'Minha localização',
    }),

  resetLocation: () => set(DEFAULT_LOCATION),
}))
