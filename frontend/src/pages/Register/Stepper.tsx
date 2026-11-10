import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const steps = [
  { number: 1, label: 'Conta' },
  { number: 2, label: 'Telefone' },
  { number: 3, label: 'Endereço' },
] as const

interface StepperProps {
  current: 1 | 2 | 3
}

export function Stepper({ current }: StepperProps) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-medium text-ink-soft">
          Etapa {current} de {steps.length}
        </span>
        <span className="text-[11px] font-semibold text-primary">
          {current === 3 ? 'Finalizar' : 'Criar conta'}
        </span>
      </div>

      <div
        role="progressbar"
        aria-label="Progresso do cadastro"
        aria-valuemin={1}
        aria-valuemax={steps.length}
        aria-valuenow={current}
        className="h-1.5 overflow-hidden rounded-full bg-gray-100"
      >
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${(current / steps.length) * 100}%` }}
        />
      </div>

      <ol className="mt-3 flex items-start justify-between">
        {steps.map((step) => {
          const completed = step.number < current
          const active = step.number === current

          return (
            <li
              key={step.number}
              aria-current={active ? 'step' : undefined}
              className="flex flex-1 flex-col items-center gap-1"
            >
              <span
                className={cn(
                  'flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold transition-colors',
                  completed || active
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-ink-soft',
                  active && 'ring-4 ring-primary/10'
                )}
              >
                {completed ? (
                  <Check size={14} aria-hidden="true" />
                ) : (
                  step.number
                )}
              </span>
              <span
                className={cn(
                  'text-[11px]',
                  active
                    ? 'font-semibold text-ink'
                    : completed
                      ? 'font-medium text-primary'
                      : 'text-ink-soft'
                )}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
