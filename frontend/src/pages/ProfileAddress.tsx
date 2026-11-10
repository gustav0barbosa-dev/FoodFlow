import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  addressLocationLabel,
  EMPTY_ADDRESS,
  formatAddress,
  hasAddressErrors,
  validateAddress,
  type AddressFields,
  type AddressMode,
  type Coordinates,
} from '@/lib/address'
import {
  accountErrorMessage,
  isAccountApiUnavailable,
  updateUserAddress,
} from '@/lib/accountApi'
import { onlyDigits } from '@/lib/validation'
import { useAddressStore } from '@/store/addressStore'
import { useAuth } from '@/contexts/AuthContext'
import { useLocationStore } from '@/store/locationStore'
import { AddressForm } from '@/components/address/AddressForm'

export function ProfileAddress() {
  const navigate = useNavigate()
  const { user, token, isDemo, updateUser } = useAuth()
  const storedAddress = user?.address
  const storedCoordinates = user?.coordinates ?? null
  const setDeliveryAddress = useAddressStore((state) => state.setAddress)
  const setLocation = useLocationStore((state) => state.setLocation)

  const [address, setAddress] = useState<AddressFields>({
    ...EMPTY_ADDRESS,
    ...storedAddress,
  })
  const [coordinates, setCoordinates] = useState<Coordinates | null>(
    storedCoordinates
  )
  const [mode, setMode] = useState<AddressMode>('manual')
  const [showErrors, setShowErrors] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const allowCoordinatesOnly = mode === 'location' && coordinates !== null
  const errors = validateAddress(address, { allowCoordinatesOnly })

  const updateAddress = (patch: Partial<AddressFields>) => {
    setAddress((current) => ({ ...current, ...patch }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setShowErrors(true)

    if (hasAddressErrors(errors)) return

    const effectiveCoordinates = mode === 'location' ? coordinates : null
    setSubmitting(true)

    try {
      if (!isDemo && token) {
        await updateUserAddress(token, {
          ...address,
          cep: onlyDigits(address.cep),
          latitude: effectiveCoordinates?.lat,
          longitude: effectiveCoordinates?.lon,
        })
      }

      const formatted = formatAddress(address)

      updateUser({ address, coordinates: effectiveCoordinates })

      if (formatted) {
        setDeliveryAddress(formatted)
      } else if (effectiveCoordinates) {
        setDeliveryAddress(
          `Localização atual (${effectiveCoordinates.lat.toFixed(5)}, ${effectiveCoordinates.lon.toFixed(5)})`
        )
      }

      if (effectiveCoordinates) {
        setLocation({
          ...effectiveCoordinates,
          label: addressLocationLabel(address),
        })
      }

      toast.success('Endereço atualizado com sucesso!')
      navigate('/perfil')
    } catch (error) {
      if (isAccountApiUnavailable(error)) {
        const formatted = formatAddress(address)

        updateUser({ address, coordinates: effectiveCoordinates })

        if (formatted) {
          setDeliveryAddress(formatted)
        } else if (effectiveCoordinates) {
          setDeliveryAddress(
            `Localização atual (${effectiveCoordinates.lat.toFixed(5)}, ${effectiveCoordinates.lon.toFixed(5)})`
          )
        }

        if (effectiveCoordinates) {
          setLocation({
            ...effectiveCoordinates,
            label: addressLocationLabel(address),
          })
        }

        toast.info('Endereço salvo localmente (modo demonstração).')
        navigate('/perfil')
        return
      }

      toast.error(accountErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full flex-col bg-white sm:h-[92vh]">
      <header className="shrink-0 border-b border-gray-100 px-4 py-4">
        <div className="mx-auto flex w-full max-w-[480px] items-center gap-2">
          <button
            type="button"
            onClick={() => navigate('/perfil')}
            aria-label="Voltar para o perfil"
            className="flex h-9 w-9 items-center justify-center rounded-full text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <ChevronLeft size={22} aria-hidden="true" />
          </button>
          <div>
            <h1 className="font-display text-lg font-bold text-ink">
              Alterar endereço
            </h1>
            <p className="text-xs text-ink-soft">
              Atualize onde você quer receber seus pedidos.
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto w-full max-w-[480px]">
          {isDemo && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-900">
              <strong>Modo demonstração.</strong> O backend ainda não possui
              endpoints de endereço. A alteração fica salva neste navegador.
            </div>
          )}

          <form id="edit-address-form" noValidate onSubmit={handleSubmit}>
            <AddressForm
              mode={mode}
              onModeChange={setMode}
              value={address}
              onChange={updateAddress}
              coordinates={coordinates}
              onCoordinatesChange={setCoordinates}
              errors={errors}
              showErrors={showErrors}
              disabled={submitting}
            />
          </form>
        </div>
      </div>

      <footer className="shrink-0 border-t border-gray-100 bg-white px-4 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3">
        <div className="mx-auto w-full max-w-[480px]">
          <button
            type="submit"
            form="edit-address-form"
            disabled={submitting}
            aria-busy={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary py-3.5 font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            {submitting && (
              <Loader2 size={18} className="animate-spin" aria-hidden="true" />
            )}
            {submitting ? 'Salvando…' : 'Salvar endereço'}
          </button>
        </div>
      </footer>
    </div>
  )
}
