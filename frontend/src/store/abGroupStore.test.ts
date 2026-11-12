import { beforeEach, describe, expect, it } from 'vitest'
import { useABGroupStore } from '@/store/abGroupStore'
import { DEFAULT_AB_GROUP, DEFAULT_EXPERIMENT_MODE } from '@/lib/config'

describe('abGroupStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useABGroupStore.setState({
      group: DEFAULT_AB_GROUP,
      mode: DEFAULT_EXPERIMENT_MODE,
    })
  })

  it('inicia com o grupo e o modo padrão do ambiente', () => {
    expect(useABGroupStore.getState().group).toBe(DEFAULT_AB_GROUP)
    expect(useABGroupStore.getState().mode).toBe(DEFAULT_EXPERIMENT_MODE)
    expect(DEFAULT_EXPERIMENT_MODE).toBe('experiment')
  })

  it('persiste o grupo escolhido no localStorage', () => {
    useABGroupStore.getState().setGroup('distance')

    expect(useABGroupStore.getState().group).toBe('distance')
    const raw = localStorage.getItem('foodflow-ab-group')
    expect(raw).not.toBeNull()
    expect(JSON.parse(raw as string).state.group).toBe('distance')
  })

  it('aceita os três grupos do experimento', () => {
    for (const group of ['baseline', 'personalized', 'distance'] as const) {
      useABGroupStore.getState().setGroup(group)
      expect(useABGroupStore.getState().group).toBe(group)
    }
  })

  it('separa demonstração do experimento oficial e persiste o modo', () => {
    useABGroupStore.getState().setMode('demo')

    expect(useABGroupStore.getState().mode).toBe('demo')
    const raw = localStorage.getItem('foodflow-ab-group')
    expect(JSON.parse(raw as string).state.mode).toBe('demo')

    useABGroupStore.getState().setMode('experiment')
    expect(useABGroupStore.getState().mode).toBe('experiment')
  })
})
