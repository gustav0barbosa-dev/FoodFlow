import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  DEFAULT_AB_GROUP,
  DEFAULT_EXPERIMENT_MODE,
  type ABGroup,
  type ExperimentMode,
} from '@/lib/config'

interface ABGroupState {
  group: ABGroup
  mode: ExperimentMode
  setGroup: (group: ABGroup) => void
  setMode: (mode: ExperimentMode) => void
}

/**
 * Estado do experimento A/B.
 *
 * ``mode`` separa demonstração de experimento oficial:
 * - no modo ``experiment`` o grupo é atribuído e persistido pelo backend;
 *   ``group`` é ignorado;
 * - no modo ``demo`` o usuário escolhe a estratégia manualmente e os eventos
 *   são marcados como demonstração, fora das métricas oficiais.
 *
 * Persistido no navegador para que a Home use o mesmo modo entre recarregamentos.
 */
export const useABGroupStore = create<ABGroupState>()(
  persist(
    (set) => ({
      group: DEFAULT_AB_GROUP,
      mode: DEFAULT_EXPERIMENT_MODE,
      setGroup: (group) => set({ group }),
      setMode: (mode) => set({ mode }),
    }),
    {
      name: 'foodflow-ab-group',
      partialize: (state) => ({ group: state.group, mode: state.mode }),
    }
  )
)
