import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  addressLocationLabel,
  formatAddress,
  hasAddressErrors,
  type AddressErrors,
  type AddressFields,
  type AddressMode,
  type Coordinates,
  EMPTY_ADDRESS,
  validateAddress,
} from '@/lib/address'
import {
  accountErrorMessage,
  createDemoSession,
  isAccountApiUnavailable,
  registerUser,
  updateUserAddress,
  updateUserPhone,
} from '@/lib/accountApi'
import {
  onlyDigits,
  validateEmail,
  validatePassword,
  validatePhone,
} from '@/lib/validation'
import { useAddressStore } from '@/store/addressStore'
import { useAuth } from '@/contexts/AuthContext'
import { useLocationStore } from '@/store/locationStore'
import { Stepper } from './Stepper'
import {
  StepAccount,
  type AccountFormErrors,
  type AccountFormValues,
} from './StepAccount'
import { StepAddress } from './StepAddress'
import { StepPhone } from './StepPhone'

type Step = 1 | 2 | 3

const initialAccount: AccountFormValues = { email: '', password: '' }

export function Register() {
  const navigate = useNavigate()
  const { login, updateUser, token, isDemo } = useAuth()
  const setDeliveryAddress = useAddressStore((state) => state.setAddress)
  const setLocation = useLocationStore((state) => state.setLocation)

  const [step, setStep] = useState<Step>(1)
  const [account, setAccount] = useState<AccountFormValues>(initialAccount)
  const [phone, setPhone] = useState('')
  const [mode, setMode] = useState<AddressMode>('location')
  const [address, setAddress] = useState<AddressFields>(EMPTY_ADDRESS)
  const [coordinates, setCoordinates] = useState<Coordinates | null>(null)
  const [registeredEmail, setRegisteredEmail] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [showErrors, setShowErrors] = useState(false)

  const accountErrors: AccountFormErrors = {
    email: validateEmail(account.email) ?? undefined,
    password: validatePassword(account.password) ?? undefined,
  }
  const phoneError = validatePhone(phone) ?? undefined
  const allowCoordinatesOnly = mode === 'location' && coordinates !== null
  const addressErrors: AddressErrors = validateAddress(address, {
    allowCoordinatesOnly,
  })

  const goBack = () => {
    setShowErrors(false)

    if (step > 1) {
      setStep((step - 1) as Step)
      return
    }

    navigate('/')
  }

  const updateAccount = (field: keyof AccountFormValues, value: string) => {
    setAccount((current) => ({ ...current, [field]: value }))
  }

  const updateAddress = (patch: Partial<AddressFields>) => {
    setAddress((current) => ({ ...current, ...patch }))
  }

  const handleAccountContinue = async () => {
    if (accountErrors.email || accountErrors.password) return

    const email = account.email.trim().toLowerCase()

    if (registeredEmail === email) {
      setStep(2)
      setShowErrors(false)
      return
    }

    setSubmitting(true)

    try {
      const session = await registerUser({ email, password: account.password })

      if (!session.token) {
        toast.error(
          'O servidor não retornou um token de acesso. Tente novamente.'
        )
        return
      }

      login(session.token, session.user)
      setRegisteredEmail(email)
      toast.success('Conta criada com sucesso!')
      setStep(2)
      setShowErrors(false)
    } catch (error) {
      if (isAccountApiUnavailable(error)) {
        const session = createDemoSession(email)
        login(session.token, session.user, { demo: true })
        setRegisteredEmail(email)
        toast.info(
          'Modo demonstração ativado: o backend ainda não possui cadastro. Seus dados ficam salvos neste navegador.'
        )
        setStep(2)
        setShowErrors(false)
        return
      }

      toast.error(accountErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  const handlePhoneContinue = async () => {
    if (phoneError) return

    setSubmitting(true)

    try {
      if (!isDemo && token) {
        await updateUserPhone(token, phone)
      }

      updateUser({ phone })
      toast.success('Telefone salvo!')
      setStep(3)
      setShowErrors(false)
    } catch (error) {
      if (isAccountApiUnavailable(error)) {
        updateUser({ phone })
        toast.info('Telefone salvo localmente (modo demonstração).')
        setStep(3)
        setShowErrors(false)
        return
      }

      toast.error(accountErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  const handleFinish = async () => {
    const effectiveCoordinates = mode === 'location' ? coordinates : null
    const errors = validateAddress(address, {
      allowCoordinatesOnly: effectiveCoordinates !== null,
    })

    if (hasAddressErrors(errors)) return

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

      toast.success('Cadastro concluído! Bem-vindo ao FoodFlow.')
      navigate('/home', { replace: true })
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
        navigate('/home', { replace: true })
        return
      }

      toast.error(accountErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  const handleContinue = () => {
    setShowErrors(true)

    if (step === 1) {
      void handleAccountContinue()
      return
    }

    if (step === 2) {
      void handlePhoneContinue()
      return
    }

    void handleFinish()
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return
    handleContinue()
  }

  return (
    <div className="flex h-full flex-col bg-white sm:h-[92vh]">
      <header className="shrink-0 border-b border-gray-100 px-4 pb-4 pt-3">
        <div className="mx-auto w-full max-w-[480px]">
          <div className="mb-3 flex items-center gap-2">
            <button
              type="button"
              onClick={goBack}
              aria-label={step > 1 ? 'Voltar para a etapa anterior' : 'Voltar'}
              className="flex h-9 w-9 items-center justify-center rounded-full text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <ChevronLeft size={22} aria-hidden="true" />
            </button>

            <div className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-sm text-white"
              >
                🍴
              </span>
              <span className="font-display font-bold text-ink">FoodFlow</span>
            </div>

            <span className="ml-auto text-xs text-ink-soft">Criar conta</span>
          </div>

          <Stepper current={step} />
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="mx-auto w-full max-w-[480px]">
          {isDemo && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-900">
              <strong>Modo demonstração.</strong> O backend ainda não possui
              endpoints de cadastro. Seus dados são salvos apenas neste
              navegador.
            </div>
          )}

          <form id="register-form" noValidate onSubmit={handleSubmit}>
            {step === 1 && (
              <StepAccount
                value={account}
                onChange={updateAccount}
                errors={accountErrors}
                showErrors={showErrors}
                disabled={submitting}
              />
            )}

            {step === 2 && (
              <StepPhone
                value={phone}
                onChange={setPhone}
                error={phoneError}
                showErrors={showErrors}
                disabled={submitting}
              />
            )}

            {step === 3 && (
              <StepAddress
                mode={mode}
                onModeChange={setMode}
                value={address}
                onChange={updateAddress}
                coordinates={coordinates}
                onCoordinatesChange={setCoordinates}
                errors={addressErrors}
                showErrors={showErrors}
                disabled={submitting}
              />
            )}
          </form>
        </div>
      </div>

      <footer className="shrink-0 border-t border-gray-100 bg-white px-4 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-3">
        <div className="mx-auto w-full max-w-[480px]">
          <button
            type="submit"
            form="register-form"
            disabled={submitting}
            aria-busy={submitting}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-primary py-3.5 font-semibold text-white transition-colors hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            {submitting && (
              <Loader2 size={18} className="animate-spin" aria-hidden="true" />
            )}
            {submitting
              ? 'Salvando…'
              : step === 3
                ? 'Finalizar cadastro'
                : 'Continuar'}
          </button>

          <p className="mt-2 text-center text-[10px] text-ink-soft">
            Etapa {step} de 3 · Você pode voltar a qualquer momento
          </p>
        </div>
      </footer>
    </div>
  )
}
