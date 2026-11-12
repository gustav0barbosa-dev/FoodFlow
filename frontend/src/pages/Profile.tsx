import { Link, useNavigate } from 'react-router-dom'
import { ChevronRight, Heart, LogOut, MapPin } from 'lucide-react'
import { currentUser } from '@/data/mockData'
import { formatAddress } from '@/lib/address'
import { useAddressStore } from '@/store/addressStore'
import { useAuth } from '@/contexts/AuthContext'
import { useFavoritesStore } from '@/store/favoritesStore'
import { EventsPanel } from '@/components/profile/EventsPanel'
import { DietaryPreferences } from '@/components/profile/DietaryPreferences'
import { ProfileStats } from '@/components/profile/ProfileStats'
import { SettingsList } from '@/components/profile/SettingsList'
import { ExperimentPanel } from '@/components/profile/ExperimentPanel'
import { TrainingMetricsPanel } from '@/components/profile/TrainingMetricsPanel'
import { useABGroupStore } from '@/store/abGroupStore'
import type { ABGroup, ExperimentMode } from '@/lib/config'
import { toast } from 'sonner'

const GROUP_TOAST: Record<string, string> = {
  '': 'Padrão do backend (atribuição automática)',
  baseline: 'Baseline (popularidade)',
  personalized: 'Personalizado (ML)',
  distance: 'Por distância',
}

export function Profile() {
  const navigate = useNavigate()
  const favoriteCount = useFavoritesStore((s) => s.favoriteIds.length)
  const { user: authUser, logout } = useAuth()
  const structuredAddress = authUser?.address
  const deliveryAddress = useAddressStore((s) => s.address)
  const displayName = authUser?.name?.trim() || currentUser.name
  const displayEmail = authUser?.email || currentUser.email
  const addressLabel = structuredAddress
    ? formatAddress(structuredAddress)
    : deliveryAddress
  const abGroup = useABGroupStore((s) => s.group)
  const setABGroup = useABGroupStore((s) => s.setGroup)
  const experimentMode = useABGroupStore((s) => s.mode)
  const setExperimentMode = useABGroupStore((s) => s.setMode)

  const handleGroupChange = (value: ABGroup) => {
    if (experimentMode !== 'demo') {
      toast.warning(
        'A seleção manual só está disponível no modo de demonstração.'
      )
      return
    }
    setABGroup(value)
    toast.info(`Estratégia de demonstração: ${GROUP_TOAST[value]}`)
  }

  const handleModeChange = (value: ExperimentMode) => {
    setExperimentMode(value)
    toast.info(
      value === 'demo'
        ? 'Modo demonstração ativado: os eventos não contam nas métricas oficiais.'
        : 'Modo experimental ativado: a atribuição é persistente pelo backend.'
    )
  }

  const handleLogout = () => {
    logout()
    toast.success('Você saiu da conta')
    navigate('/', { replace: true })
  }

  return (
    <div className="h-full overflow-y-auto pb-6 bg-surface-muted">
      <header className="bg-white px-4 py-6 border-b border-gray-100 flex items-center gap-3">
        <div className="w-14 h-14 rounded-full bg-primary text-white flex items-center justify-center text-xl font-bold">
          {displayName.trim()[0]?.toUpperCase() ?? '?'}
        </div>
        <div>
          <h1 className="font-display font-bold text-lg text-ink">{displayName}</h1>
          <p className="text-xs text-ink-soft">{displayEmail}</p>
        </div>
      </header>

      <div className="p-4 space-y-3 sm:max-w-[700px] sm:mx-auto">
        <ProfileStats />

        <Link
          to="/perfil/endereco"
          className="block bg-white rounded-2xl p-4 border border-gray-100 hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="flex items-center gap-1.5 font-semibold text-ink">
                <MapPin size={16} className="text-primary" aria-hidden="true" />
                Endereço de entrega
              </h2>
              <p className="mt-1 text-sm text-ink-soft break-words">
                {addressLabel || 'Nenhum endereço cadastrado'}
              </p>
            </div>
            <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-primary">
              Alterar
              <ChevronRight size={14} aria-hidden="true" />
            </span>
          </div>
        </Link>

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

        <ExperimentPanel
          group={abGroup}
          mode={experimentMode}
          onGroupChange={handleGroupChange}
          onModeChange={handleModeChange}
        />

        <TrainingMetricsPanel />

        <section className="bg-white rounded-2xl p-4 border border-gray-100">
          <h2 className="font-semibold text-ink mb-1">Suas preferências de recomendação</h2>
          <p className="text-xs text-ink-soft">
            Essas preferências ajudam a personalizar suas recomendações.
          </p>
          {/* TODO: sliders de faixa de preço, chips de culinária favorita */}
        </section>

        <EventsPanel />

        <SettingsList />

        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full items-center justify-center gap-2 rounded-2xl border border-red-200 bg-white px-4 py-3 text-sm font-semibold text-red-600 transition-colors hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
        >
          <LogOut size={16} aria-hidden="true" />
          Sair da conta
        </button>
      </div>
    </div>
  )
}
