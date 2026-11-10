import { useState } from 'react'
import { Phone } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatPhone } from '@/lib/validation'

interface StepPhoneProps {
  value: string
  onChange: (value: string) => void
  error?: string
  showErrors: boolean
  disabled?: boolean
}

export function StepPhone({
  value,
  onChange,
  error,
  showErrors,
  disabled = false,
}: StepPhoneProps) {
  const [touched, setTouched] = useState(false)
  const visibleError = touched || showErrors ? error : undefined

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">
          Qual é o seu telefone?
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Usamos seu número para confirmar pedidos e avisar sobre a entrega.
        </p>
      </div>

      <div>
        <label
          htmlFor="register-phone"
          className="mb-1 block text-xs font-medium text-ink-soft"
        >
          Telefone com DDD
        </label>
        <div className="relative">
          <Phone
            size={16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-soft"
          />
          <input
            id="register-phone"
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            value={value}
            disabled={disabled}
            onChange={(event) => onChange(formatPhone(event.target.value))}
            onBlur={() => setTouched(true)}
            placeholder="(11) 99999-9999"
            maxLength={15}
            aria-invalid={visibleError ? true : undefined}
            aria-describedby={
              visibleError ? 'register-phone-error' : 'register-phone-helper'
            }
            className={cn(
              'w-full rounded-xl border bg-white py-2.5 pl-9 pr-3 text-sm text-ink placeholder:text-ink-soft/70',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
              visibleError ? 'border-primary-dark' : 'border-gray-200',
              disabled && 'opacity-60'
            )}
          />
        </div>
        {visibleError ? (
          <p
            id="register-phone-error"
            role="alert"
            className="mt-1 text-[11px] text-primary-dark"
          >
            {visibleError}
          </p>
        ) : (
          <p id="register-phone-helper" className="mt-1 text-[11px] text-ink-soft">
            Ex.: (11) 99999-9999. Pode ser celular ou telefone fixo.
          </p>
        )}
      </div>

      <div className="rounded-2xl bg-surface-muted p-3 text-[11px] leading-relaxed text-ink-soft">
        Seu telefone não aparece para outros clientes nem para os restaurantes.
      </div>
    </div>
  )
}
