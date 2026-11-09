import { create } from 'zustand'

export const DEFAULT_ADDRESS = 'R. das Flores, 123 — Osasco, SP'

interface AddressState {
  address: string
  setAddress: (address: string) => void
}

export const useAddressStore = create<AddressState>((set) => ({
  address: DEFAULT_ADDRESS,

  setAddress: (address) => {
    const trimmed = address.trim()
    if (trimmed.length === 0) return
    set({ address: trimmed })
  },
}))
