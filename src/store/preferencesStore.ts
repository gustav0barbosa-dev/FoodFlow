import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { DietaryPreference } from '@/types'
import { DIETARY_PREFERENCES } from '@/types'

export { DIETARY_PREFERENCES }
export type { DietaryPreference }

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
