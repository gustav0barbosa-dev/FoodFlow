import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AccountUser, AuthSession } from '@/lib/accountApi'
import type { AddressFields, Coordinates } from '@/lib/address'

interface AuthState {
  token: string | null
  user: AccountUser | null
  /** Sessão local usada enquanto o backend não oferece cadastro/login. */
  isDemo: boolean
  setSession: (session: AuthSession, options?: { demo?: boolean }) => void
  setPhone: (phone: string) => void
  setAddress: (
    address: AddressFields,
    coordinates?: Coordinates | null
  ) => void
  updateUser: (patch: Partial<AccountUser>) => void
  signOut: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isDemo: false,

      setSession: (session, options) =>
        set({
          token: session.token,
          user: session.user,
          isDemo: options?.demo ?? false,
        }),

      setPhone: (phone) =>
        set((state) =>
          state.user
            ? { user: { ...state.user, phone } }
            : { user: { id: '', email: '', phone } }
        ),

      setAddress: (address, coordinates) =>
        set((state) => {
          if (!state.user) return state

          return {
            user: {
              ...state.user,
              address,
              coordinates:
                coordinates === undefined
                  ? state.user.coordinates ?? null
                  : coordinates,
            },
          }
        }),

      updateUser: (patch) =>
        set((state) =>
          state.user ? { user: { ...state.user, ...patch } } : state
        ),

      signOut: () => set({ token: null, user: null, isDemo: false }),
    }),
    {
      name: 'foodflow-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isDemo: state.isDemo,
      }),
    }
  )
)
