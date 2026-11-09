import { describe, expect, it, beforeEach, vi } from 'vitest'
import { getCurrentTurno, isUuid } from '@/lib/config'

describe('config', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('retorna manha entre 05:00 e 11:59 (horário de Brasília)', () => {
    // 09:00 UTC-3 = 12:00 UTC
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 1, 12, 0, 0)))
    expect(getCurrentTurno()).toBe('manha')
  })

  it('retorna tarde entre 12:00 e 17:59 (horário de Brasília)', () => {
    // 15:00 UTC-3 = 18:00 UTC
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 1, 18, 0, 0)))
    expect(getCurrentTurno()).toBe('tarde')
  })

  it('retorna noite entre 18:00 e 23:59 (horário de Brasília)', () => {
    // 21:00 UTC-3 = 00:00 UTC no dia seguinte
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 2, 0, 0, 0)))
    expect(getCurrentTurno()).toBe('noite')
  })

  it('retorna madrugada entre 00:00 e 04:59 (horário de Brasília)', () => {
    // 02:00 UTC-3 = 05:00 UTC
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 1, 5, 0, 0)))
    expect(getCurrentTurno()).toBe('madrugada')
  })

  it('identifica UUIDs válidos', () => {
    expect(isUuid('a54a52c3-8543-56d3-8e4b-6d8220667bd5')).toBe(true)
    expect(isUuid('not-a-uuid')).toBe(false)
    expect(isUuid(undefined)).toBe(false)
    expect(isUuid(null)).toBe(false)
  })
})
