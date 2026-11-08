import { currentUser } from '@/data/mockData'
import { EventsPanel } from '@/components/profile/EventsPanel'
import { DietaryPreferences } from '@/components/profile/DietaryPreferences'
import { SettingsList } from '@/components/profile/SettingsList'

export function Profile() {
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
        <DietaryPreferences />

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-semibold text-ink mb-1">Suas preferências de recomendação</h2>
          <p className="text-xs text-ink-soft">
            Essas preferências ajudam a personalizar suas recomendações.
          </p>
          {/* TODO: sliders de faixa de preço, chips de culinária favorita */}
        </section>

        <EventsPanel />

        <SettingsList />
      </div>
    </div>
  )
}
