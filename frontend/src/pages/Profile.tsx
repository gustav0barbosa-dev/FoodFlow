import { Link } from 'react-router-dom'
import { useState } from 'react'
import { Heart } from 'lucide-react'
import { currentUser } from '@/data/mockData'
import { useFavoritesStore } from '@/store/favoritesStore'
import { EventsPanel } from '@/components/profile/EventsPanel'
import { DietaryPreferences } from '@/components/profile/DietaryPreferences'
import { ProfileStats } from '@/components/profile/ProfileStats'
import { SettingsList } from '@/components/profile/SettingsList'
import { getABGroup, type ABGroup } from '@/lib/config'
import { getABTestResults as fetchABTestResults } from '@/lib/api'
import { toast } from 'sonner'

export function Profile() {
  const favoriteCount = useFavoritesStore((s) => s.favoriteIds.length)
  const [abGroup, setABGroup] = useState<ABGroup>(getABGroup())
  const [abResults, setABResults] = useState<{
    redis_available: boolean
    total_requests: number
    personalized_requests: number
    distance_requests: number
    personalized_share: number
    distance_share: number
  } | null>(null)
  const [loadingResults, setLoadingResults] = useState(false)

  const handleGroupChange = (value: string) => {
    const next = value as ABGroup
    setABGroup(next)
    toast.info(
      `Grupo do experimento alterado para: ${next === 'personalized' ? 'Recomendações personalizadas' : next === 'distance' ? 'Por distância' : 'Padrão do backend'}`
    )
  }

  const loadABResults = async () => {
    setLoadingResults(true)
    try {
      const results = await fetchABTestResults()
      setABResults(results)
    } catch {
      // Sem API, os resultados não estão disponíveis.
      setABResults(null)
    } finally {
      setLoadingResults(false)
    }
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

      <div className="p-4 space-y-3 sm:max-w-[700px] sm:mx-auto">
        <ProfileStats />
        <DietaryPreferences />

        <Link
          to="/favoritos"
          className="flex items-center justify-between bg-white rounded-2xl p-4 border border-gray-100 hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <span className="flex items-center gap-2 text-sm font-medium text-ink">
            <Heart size={16} className="text-primary" />
            Favoritos
          </span>
          <span className="text-xs text-ink-soft">
            {favoriteCount === 0
              ? 'Nenhum salvo'
              : `${favoriteCount} ${
                  favoriteCount === 1 ? 'restaurante salvo' : 'restaurantes salvos'
                }`}
          </span>
        </Link>

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-semibold text-ink mb-1">
            Experimento A/B de recomendações
          </h2>
          <p className="text-xs text-ink-soft mb-3">
            Escolha qual estratégia de recomendação deseja receber. A escolha
            persiste apenas nesta sessão (ou via VITE_AB_GROUP em produção).
          </p>
          <div className="flex flex-wrap gap-2 mb-3">
            {(['', 'personalized', 'distance'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => handleGroupChange(value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  abGroup === value
                    ? 'bg-primary border-primary text-white'
                    : 'bg-white border-gray-200 text-ink-soft hover:bg-surface-muted'
                }`}
              >
                {value === ''
                  ? 'Padrão (backend)'
                  : value === 'personalized'
                  ? 'Personalizado (ML)'
                  : 'Por distância'}
              </button>
            ))}
          </div>
          {abResults && (
            <div className="bg-surface-muted rounded-xl p-3 mt-3">
              <h3 className="text-xs font-semibold text-ink-soft mb-2">
                Resultados acumulados
              </h3>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-white p-2 rounded border border-gray-100">
                  <dt className="text-[10px] text-ink-soft">Total</dt>
                  <dd className="text-ink font-medium">{abResults.total_requests}</dd>
                </div>
                <div className="bg-white p-2 rounded border border-gray-100">
                  <dt className="text-[10px] text-ink-soft">Personalizado</dt>
                  <dd className="text-ink font-medium">
                    {abResults.personalized_requests} (
                    {abResults.personalized_share * 100}%
                    )
                  </dd>
                </div>
                <div className="bg-white p-2 rounded border border-gray-100">
                  <dt className="text-[10px] text-ink-soft">Por distância</dt>
                  <dd className="text-ink font-medium">
                    {abResults.distance_requests} (
                    {abResults.distance_share * 100}%
                    )
                  </dd>
                </div>
              </dl>
            </div>
          )}
          {!abResults && !loadingResults && (
            <button
              type="button"
              onClick={loadABResults}
              className="text-xs text-primary underline hover:text-primary-dark"
            >
              Carregar resultados do experimento
            </button>
          )}
          {loadingResults && (
            <p className="text-xs text-ink-soft">Carregando…</p>
          )}
        </section>

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
