import { useState } from 'react'
import { Eye, EyeOff, LockKeyhole, Mail } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface AccountFormValues {
  email: string
  password: string
}

export type AccountFormErrors = Partial<Record<keyof AccountFormValues, string>>

interface StepAccountProps {
  value: AccountFormValues
  onChange: (field: keyof AccountFormValues, fieldValue: string) => void
  errors: AccountFormErrors
  showErrors: boolean
  disabled?: boolean
}

export function StepAccount({
  value,
  onChange,
  errors,
  showErrors,
  disabled = false,
}: StepAccountProps) {
  const [touched, setTouched] = useState<Partial<Record<keyof AccountFormValues, boolean>>>({})
  const [passwordVisible, setPasswordVisible] = useState(false)

  const errorFor = (field: keyof AccountFormValues) =>
    touched[field] || showErrors ? errors[field] : undefined

  const markTouched = (field: keyof AccountFormValues) =>
    setTouched((current) => ({ ...current, [field]: true }))

  const emailError = errorFor('email')
  const passwordError = errorFor('password')

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">
          Crie sua conta
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Use seu e-mail e uma senha para começar a pedir.
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <label
            htmlFor="register-email"
            className="mb-1 block text-xs font-medium text-ink-soft"
          >
            E-mail
          </label>
          <div className="relative">
            <Mail
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft"
            />
            <input
              id="register-email"
              type="email"
              inputMode="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              value={value.email}
              disabled={disabled}
              onChange={(event) => onChange('email', event.target.value)}
              onBlur={() => markTouched('email')}
              placeholder="voce@exemplo.com"
              aria-invalid={emailError ? true : undefined}
              aria-describedby={emailError ? 'register-email-error' : undefined}
              className={cn(
                'w-full rounded-xl border bg-white py-2.5 pl-9 pr-3 text-sm text-ink placeholder:text-ink-soft/70',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
                emailError ? 'border-primary-dark' : 'border-gray-200',
                disabled && 'opacity-60'
              )}
            />
          </div>
          {emailError && (
            <p
              id="register-email-error"
              role="alert"
              className="mt-1 text-[11px] text-primary-dark"
            >
              {emailError}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="register-password"
            className="mb-1 block text-xs font-medium text-ink-soft"
          >
            Senha
          </label>
          <div className="relative">
            <LockKeyhole
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft"
            />
            <input
              id="register-password"
              type={passwordVisible ? 'text' : 'password'}
              autoComplete="new-password"
              value={value.password}
              disabled={disabled}
              onChange={(event) => onChange('password', event.target.value)}
              onBlur={() => markTouched('password')}
              placeholder="Mínimo de 8 caracteres"
              aria-invalid={passwordError ? true : undefined}
              aria-describedby={
                passwordError ? 'register-password-error' : 'register-password-helper'
              }
              className={cn(
                'w-full rounded-xl border bg-white py-2.5 pl-9 pr-11 text-sm text-ink placeholder:text-ink-soft/70',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
                passwordError ? 'border-primary-dark' : 'border-gray-200',
                disabled && 'opacity-60'
              )}
            />
            <button
              type="button"
              onClick={() => setPasswordVisible((visible) => !visible)}
              disabled={disabled}
              aria-label={passwordVisible ? 'Ocultar senha' : 'Mostrar senha'}
              className="absolute right-1.5 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-ink-soft hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
            >
              {passwordVisible ? (
                <EyeOff size={16} aria-hidden="true" />
              ) : (
                <Eye size={16} aria-hidden="true" />
              )}
            </button>
          </div>
          {passwordError ? (
            <p
              id="register-password-error"
              role="alert"
              className="mt-1 text-[11px] text-primary-dark"
            >
              {passwordError}
            </p>
          ) : (
            <p
              id="register-password-helper"
              className="mt-1 text-[11px] text-ink-soft"
            >
              Use pelo menos 8 caracteres.
            </p>
          )}
        </div>
      </div>

      <div className="rounded-2xl bg-surface-muted p-3 text-[11px] leading-relaxed text-ink-soft">
        Ao continuar, você cria sua conta FoodFlow. Você poderá adicionar seu
        telefone e endereço nas próximas etapas.
      </div>
    </div>
  )
}
