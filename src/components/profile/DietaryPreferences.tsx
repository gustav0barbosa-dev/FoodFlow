import { useEventsStore } from '@/store/eventsStore'
import {
  usePreferencesStore,
  DIETARY_PREFERENCES,
  type DietaryPreference,
} from '@/store/preferencesStore'
import { cn } from '@/lib/utils'

export function DietaryPreferences() {
  const preferences = usePreferencesStore((s) => s.preferences)
  const togglePreference = usePreferencesStore((s) => s.togglePreference)
  const clearPreferences = usePreferencesStore((s) => s.clearPreferences)
  const trackEvent = useEventsStore((s) => s.trackEvent)

  const handleToggle = (preference: DietaryPreference) => {
    const isSelected = preferences.includes(preference)
    const next = isSelected
      ? preferences.filter((p) => p !== preference)
      : [...preferences, preference]

    togglePreference(preference)
    trackEvent('preferences_updated', {
      action: isSelected ? 'removed' : 'added',
      preference,
      preferences: next,
    })
  }

  const handleClear = () => {
    if (preferences.length === 0) return
    clearPreferences()
    trackEvent('preferences_updated', {
      action: 'cleared',
      preferences: [],
    })
  }

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <div className="flex items-start justify-between gap-2 mb-1">
        <h2 className="font-semibold text-ink">Preferências alimentares</h2>
        {preferences.length > 0 && (
          <button
            type="button"
            onClick={handleClear}
            className="text-xs font-medium text-primary px-2 py-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Limpar
          </button>
        )}
      </div>
      <p className="text-xs text-ink-soft mb-3">
        {preferences.length === 0
          ? 'Selecione o que combina com você.'
          : `${preferences.length} ${
              preferences.length === 1
                ? 'preferência selecionada'
                : 'preferências selecionadas'
            }`}
      </p>
      <div className="flex flex-wrap gap-2">
        {DIETARY_PREFERENCES.map((preference) => {
          const isSelected = preferences.includes(preference)
          return (
            <button
              key={preference}
              type="button"
              onClick={() => handleToggle(preference)}
              aria-pressed={isSelected}
              className={cn(
                'px-3 py-1.5 rounded-full text-sm border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                isSelected
                  ? 'bg-primary/10 border-primary text-primary-dark font-medium'
                  : 'bg-surface-muted border-transparent text-ink hover:bg-gray-100'
              )}
            >
              {preference}
            </button>
          )
        })}
      </div>
    </section>
  )
}
