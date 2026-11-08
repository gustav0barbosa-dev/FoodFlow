import { currentUser } from '@/data/mockData'
import { EventsPanel } from '@/components/profile/EventsPanel'
import { useEventsStore } from '@/store/eventsStore'
import {
  usePreferencesStore,
  DIETARY_PREFERENCES,
  type DietaryPreference,
} from '@/store/preferencesStore'
import { cn } from '@/lib/utils'

export function Profile() {
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
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      <header className="bg-white px-4 py-6 border-b border-gray-100 flex items-center gap-3">
        <div className="w-14 h-14 rounded-full bg-primary text-white flex items-center justify-center text-xl font-bold">
          {currentUser.name[0]}
        </div>
        <div>
          <h1 className="font-display font-bold text-lg text-ink">{currentUser.name}</h1>
          <p className="text-xs text-ink-soft">{currentUser.email}</p>
        </div>
      </header>

      <div className="p-4 space-y-3">
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
                  preferences.length === 1 ? 'preferência selecionada' : 'preferências selecionadas'
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
                      ? 'bg-primary/10 border-primary text-primary font-medium'
                      : 'bg-surface-muted border-transparent text-ink hover:bg-gray-100'
                  )}
                >
                  {preference}
                </button>
              )
            })}
          </div>
        </section>

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-semibold text-ink mb-1">Suas preferências de recomendação</h2>
          <p className="text-xs text-ink-soft">
            Essas preferências ajudam a personalizar suas recomendações.
          </p>
          {/* TODO: sliders de faixa de preço, chips de culinária favorita */}
        </section>

        <EventsPanel />

        <section className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-100">
          {['Notificações', 'Endereços', 'Pagamento', 'Sair'].map((item) => (
            <button
              key={item}
              type="button"
              className="w-full text-left px-4 py-3 text-sm text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {item}
            </button>
          ))}
        </section>
      </div>
    </div>
  )
}
