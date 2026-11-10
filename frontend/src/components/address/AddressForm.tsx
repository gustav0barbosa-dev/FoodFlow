import {
  useEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react'
import {
  CheckCircle2,
  Loader2,
  LocateFixed,
  MapPin,
  PencilLine,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  type AddressErrors,
  type AddressField,
  type AddressFields,
  type AddressMode,
  type Coordinates,
} from '@/lib/address'
import { reverseGeocode } from '@/lib/geocoding'
import { cn } from '@/lib/utils'
import { formatCep, onlyDigits } from '@/lib/validation'
import { CepLookupError, fetchAddressByCep } from '@/lib/viacep'

export interface AddressFormProps {
  mode: AddressMode
  onModeChange: (mode: AddressMode) => void
  value: AddressFields
  onChange: (patch: Partial<AddressFields>) => void
  coordinates: Coordinates | null
  onCoordinatesChange: (coordinates: Coordinates | null) => void
  errors: AddressErrors
  showErrors: boolean
  disabled?: boolean
}

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  id: string
  label: string
  error?: string
  helper?: ReactNode
  trailing?: ReactNode
}

function TextField({
  id,
  label,
  error,
  helper,
  trailing,
  className,
  ...props
}: TextFieldProps) {
  const errorId = `${id}-error`
  const helperId = `${id}-helper`

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-medium text-ink-soft"
      >
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : helper ? helperId : undefined}
          className={cn(
            'w-full rounded-xl border bg-white px-3 py-2.5 text-sm text-ink placeholder:text-ink-soft/70 transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
            error ? 'border-primary-dark' : 'border-gray-200',
            trailing && 'pr-10',
            className
          )}
          {...props}
        />
        {trailing && (
          <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
            {trailing}
          </span>
        )}
      </div>
      {error ? (
        <p id={errorId} role="alert" className="mt-1 text-[11px] text-primary-dark">
          {error}
        </p>
      ) : helper ? (
        <p id={helperId} className="mt-1 text-[11px] text-ink-soft">
          {helper}
        </p>
      ) : null}
    </div>
  )
}

type CepStatus = 'idle' | 'loading' | 'success' | 'warning' | 'error'

export function AddressForm({
  mode,
  onModeChange,
  value,
  onChange,
  coordinates,
  onCoordinatesChange,
  errors,
  showErrors,
  disabled = false,
}: AddressFormProps) {
  const [touched, setTouched] = useState<Partial<Record<AddressField, boolean>>>({})
  const [locating, setLocating] = useState(false)
  const [locationError, setLocationError] = useState<string | null>(null)
  const [reverseStatus, setReverseStatus] = useState<
    'idle' | 'loading' | 'done' | 'failed'
  >('idle')
  const [cepStatus, setCepStatus] = useState<CepStatus>('idle')
  const [cepMessage, setCepMessage] = useState<string | null>(null)
  const cepController = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => cepController.current?.abort()
  }, [])

  const markTouched = (field: AddressField) =>
    setTouched((current) => ({ ...current, [field]: true }))

  const errorFor = (field: AddressField) =>
    touched[field] || showErrors ? errors[field] : undefined

  const updateField = (field: AddressField, fieldValue: string) => {
    onChange({ [field]: fieldValue } as Partial<AddressFields>)
    if (errors[field]) markTouched(field)
  }

  const lookupCep = async (cep: string) => {
    cepController.current?.abort()
    const controller = new AbortController()
    cepController.current = controller

    setCepStatus('loading')
    setCepMessage('Buscando endereço…')

    try {
      const result = await fetchAddressByCep(cep, controller.signal)
      if (controller.signal.aborted) return

      const patch: Partial<AddressFields> = {}
      if (result.street) patch.street = result.street
      if (result.neighborhood) patch.neighborhood = result.neighborhood
      if (result.city) patch.city = result.city
      if (result.state) patch.state = result.state
      if (result.complement && !value.complement) patch.complement = result.complement

      if (Object.keys(patch).length > 0) onChange(patch)

      setCepStatus('success')
      setCepMessage('Endereço preenchido pelo CEP. Confira o número.')
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return

      if (error instanceof CepLookupError && error.code === 'not_found') {
        setCepStatus('error')
        setCepMessage('CEP não encontrado. Confira os 8 dígitos.')
      } else {
        setCepStatus('warning')
        setCepMessage('Não foi possível buscar o CEP. Preencha os campos manualmente.')
      }
    }
  }

  const handleCepChange = (rawValue: string) => {
    const masked = formatCep(rawValue)
    updateField('cep', masked)

    if (onlyDigits(masked).length === 8) {
      void lookupCep(masked)
    } else {
      cepController.current?.abort()
      setCepStatus('idle')
      setCepMessage(null)
    }
  }

  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      const message =
        'Seu navegador não suporta geolocalização. Digite o endereço manualmente.'
      setLocationError(message)
      toast.error(message)
      return
    }

    setLocating(true)
    setLocationError(null)
    setReverseStatus('idle')

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const nextCoordinates = {
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        }

        onCoordinatesChange(nextCoordinates)
        setLocating(false)
        setReverseStatus('loading')

        const result = await reverseGeocode(
          nextCoordinates.lat,
          nextCoordinates.lon
        )

        if (!result) {
          setReverseStatus('failed')
          toast.info(
            'Localização capturada. Não foi possível preencher o endereço automaticamente; complete os campos.'
          )
          return
        }

        if (Object.keys(result.address).length > 0) {
          onChange(result.address)
        }
        setReverseStatus('done')
        toast.success('Localização capturada e endereço preenchido.')
      },
      (error) => {
        setLocating(false)

        const messages: Record<number, string> = {
          1: 'Permissão de localização negada. Você pode digitar o endereço manualmente.',
          2: 'Sua localização está indisponível no momento. Digite o endereço manualmente.',
          3: 'O tempo para obter sua localização esgotou. Tente novamente ou digite o endereço.',
        }
        const message =
          messages[error.code] ??
          'Não foi possível obter sua localização. Digite o endereço manualmente.'

        setLocationError(message)
        toast.error(message)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    )
  }

  const cepFieldError =
    errorFor('cep') ??
    (cepStatus === 'error' ? cepMessage ?? undefined : undefined)

  const cepHelper =
    cepStatus === 'success' || cepStatus === 'warning' ? cepMessage : null

  const fields = (
    <div className="space-y-3">
      <TextField
        id="address-cep"
        label="CEP"
        value={value.cep}
        onChange={(event) => handleCepChange(event.target.value)}
        onBlur={() => markTouched('cep')}
        placeholder="00000-000"
        inputMode="numeric"
        autoComplete="postal-code"
        maxLength={9}
        disabled={disabled}
        error={cepFieldError}
        helper={
          cepStatus === 'loading'
            ? 'Buscando endereço…'
            : cepHelper ?? 'Digite o CEP para preencher automaticamente.'
        }
        trailing={
          cepStatus === 'loading' ? (
            <Loader2 size={15} className="animate-spin text-ink-soft" />
          ) : undefined
        }
      />

      <TextField
        id="address-street"
        label="Rua / Avenida"
        value={value.street}
        onChange={(event) => updateField('street', event.target.value)}
        onBlur={() => markTouched('street')}
        placeholder="Ex.: Av. dos Autonomistas"
        autoComplete="address-line1"
        disabled={disabled}
        error={errorFor('street')}
      />

      <div className="grid grid-cols-2 gap-3">
        <TextField
          id="address-number"
          label="Número"
          value={value.number}
          onChange={(event) => updateField('number', event.target.value)}
          onBlur={() => markTouched('number')}
          placeholder="Ex.: 1400"
          inputMode="numeric"
          autoComplete="address-line2"
          disabled={disabled}
          error={errorFor('number')}
        />
        <TextField
          id="address-complement"
          label="Complemento (opcional)"
          value={value.complement}
          onChange={(event) => updateField('complement', event.target.value)}
          onBlur={() => markTouched('complement')}
          placeholder="Apto, bloco…"
          autoComplete="address-line3"
          disabled={disabled}
          error={errorFor('complement')}
        />
      </div>

      <TextField
        id="address-neighborhood"
        label="Bairro"
        value={value.neighborhood}
        onChange={(event) => updateField('neighborhood', event.target.value)}
        onBlur={() => markTouched('neighborhood')}
        placeholder="Ex.: Centro"
        disabled={disabled}
        error={errorFor('neighborhood')}
      />

      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <TextField
            id="address-city"
            label="Cidade"
            value={value.city}
            onChange={(event) => updateField('city', event.target.value)}
            onBlur={() => markTouched('city')}
            placeholder="Ex.: Osasco"
            autoComplete="address-level2"
            disabled={disabled}
            error={errorFor('city')}
          />
        </div>
        <TextField
          id="address-state"
          label="Estado"
          value={value.state}
          onChange={(event) =>
            updateField('state', event.target.value.toUpperCase().slice(0, 2))
          }
          onBlur={() => markTouched('state')}
          placeholder="UF"
          autoComplete="address-level1"
          maxLength={2}
          disabled={disabled}
          error={errorFor('state')}
        />
      </div>
    </div>
  )

  return (
    <div className="space-y-5">
      <div
        role="group"
        aria-label="Como informar o endereço"
        className="grid grid-cols-2 gap-1 rounded-2xl bg-surface-muted p-1"
      >
        <button
          type="button"
          aria-pressed={mode === 'location'}
          onClick={() => onModeChange('location')}
          disabled={disabled}
          className={cn(
            'flex items-center justify-center gap-1.5 rounded-xl px-2 py-2.5 text-xs font-semibold transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
            mode === 'location'
              ? 'bg-white text-primary shadow-sm'
              : 'text-ink-soft hover:text-ink',
            disabled && 'opacity-60'
          )}
        >
          <MapPin size={15} aria-hidden="true" />
          Usar minha localização
        </button>
        <button
          type="button"
          aria-pressed={mode === 'manual'}
          onClick={() => onModeChange('manual')}
          disabled={disabled}
          className={cn(
            'flex items-center justify-center gap-1.5 rounded-xl px-2 py-2.5 text-xs font-semibold transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
            mode === 'manual'
              ? 'bg-white text-primary shadow-sm'
              : 'text-ink-soft hover:text-ink',
            disabled && 'opacity-60'
          )}
        >
          <PencilLine size={15} aria-hidden="true" />
          Digitar endereço
        </button>
      </div>

      {mode === 'location' ? (
        <div className="space-y-4">
          {coordinates ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
              <div className="flex items-start gap-2">
                <CheckCircle2
                  size={18}
                  className="mt-0.5 shrink-0 text-emerald-600"
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-emerald-900">
                    Localização capturada
                  </p>
                  <p className="mt-0.5 text-[11px] text-emerald-800">
                    {coordinates.lat.toFixed(5)}, {coordinates.lon.toFixed(5)}
                  </p>
                  <p className="mt-1 text-[11px] text-emerald-800">
                    {reverseStatus === 'loading'
                      ? 'Buscando o endereço correspondente…'
                      : reverseStatus === 'done'
                        ? 'Endereço preenchido automaticamente. Confira o número.'
                        : reverseStatus === 'failed'
                          ? 'Não foi possível obter o endereço textual. Preencha os campos abaixo ou finalize apenas com a localização.'
                          : 'Confira os campos abaixo.'}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-gray-200 bg-surface-muted px-4 py-6 text-center">
              <span className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-white text-primary shadow-sm">
                <MapPin size={20} aria-hidden="true" />
              </span>
              <p className="text-sm font-medium text-ink">
                Preencha o endereço com sua localização
              </p>
              <p className="mx-auto mt-1 max-w-[280px] text-xs text-ink-soft">
                Vamos capturar latitude e longitude e tentar preencher o
                endereço automaticamente.
              </p>
            </div>
          )}

          {locationError && (
            <p role="alert" className="text-xs text-primary-dark">
              {locationError}
            </p>
          )}

          {!coordinates && showErrors && (
            <p role="alert" className="text-xs text-primary-dark">
              Use sua localização atual ou selecione “Digitar endereço” para
              continuar.
            </p>
          )}

          <button
            type="button"
            onClick={handleUseCurrentLocation}
            disabled={disabled || locating}
            className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-primary px-4 py-3 text-sm font-semibold text-primary transition-colors hover:bg-primary hover:text-white disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            {locating ? (
              <Loader2 size={17} className="animate-spin" aria-hidden="true" />
            ) : (
              <LocateFixed size={17} aria-hidden="true" />
            )}
            {locating
              ? 'Buscando sua localização…'
              : coordinates
                ? 'Atualizar localização'
                : 'Usar minha localização atual'}
          </button>

          {coordinates && fields}
        </div>
      ) : (
        fields
      )}
    </div>
  )
}
