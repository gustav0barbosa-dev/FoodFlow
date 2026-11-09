import { create } from 'zustand'

export type DietaryPreference = 'Vegano' | 'Vegetariano' | 'Sem glúten' | 'Sem lactose'

export const DIETARY_PREFERENCES: DietaryPreference[] = [
  'Vegano',
  'Vegetariano',
  'Sem glúten',
  'Sem lactose',
]

interface PreferencesState {
  preferences: DietaryPreference[]
  togglePreference: (preference: DietaryPreference) => void
  clearPreferences: () => void
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  preferences: [],

  togglePreference: (preference) =>
    set({
      preferences: get().preferences.includes(preference)
        ? get().preferences.filter((p) => p !== preference)
        : [...get().preferences, preference],
    }),

  clearPreferences: () => set({ preferences: [] }),
}))
