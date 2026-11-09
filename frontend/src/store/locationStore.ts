import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  DEFAULT_LATITUDE,
  DEFAULT_LOCATION_LABEL,
  DEFAULT_LONGITUDE,
} from '@/lib/config'

export interface LocationState {
  lat: number
  lon: number
  label: string
  setLocation: (location: { lat: number; lon: number; label?: string }) => void
  resetLocation: () => void
}

export const DEFAULT_LOCATION = {
  lat: DEFAULT_LATITUDE,
  lon: DEFAULT_LONGITUDE,
  label: DEFAULT_LOCATION_LABEL,
}

export const useLocationStore = create<LocationState>()(
  persist(
    (set) => ({
      ...DEFAULT_LOCATION,

      setLocation: ({ lat, lon, label }) =>
        set({
          lat,
          lon,
          label: label?.trim() || 'Minha localização',
        }),

      resetLocation: () => set(DEFAULT_LOCATION),
    }),
    {
      name: 'foodflow-location',
      partialize: (state) => ({
        lat: state.lat,
        lon: state.lon,
        label: state.label,
      }),
    }
  )
)
