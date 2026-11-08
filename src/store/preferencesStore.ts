import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const DIETARY_PREFERENCES = [
  'Vegano',
  'Vegetariano',
  'Sem glúten',
  'Sem lactose',
] as const

export type DietaryPreference = (typeof DIETARY_PREFERENCES)[number]

interface PreferencesState {
  preferences: DietaryPreference[]
  togglePreference: (preference: DietaryPreference) => void
  clearPreferences: () => void
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set, get) => ({
      preferences: [],

      togglePreference: (preference) =>
        set({
          preferences: get().preferences.includes(preference)
            ? get().preferences.filter((p) => p !== preference)
            : [...get().preferences, preference],
        }),

      clearPreferences: () => set({ preferences: [] }),
    }),
    {
      name: 'foodflow-preferences',
      partialize: (state) => ({ preferences: state.preferences }),
    }
  )
)
