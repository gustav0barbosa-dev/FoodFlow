import {
  AddressForm,
  type AddressFormProps,
} from '@/components/address/AddressForm'

export function StepAddress(props: AddressFormProps) {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-display text-2xl font-bold text-ink">
          Onde você quer receber seus pedidos?
        </h1>
        <p className="mt-1 text-sm text-ink-soft">
          Use sua localização atual ou digite o endereço completo.
        </p>
      </div>

      <AddressForm {...props} />

      <p className="text-[11px] leading-relaxed text-ink-soft">
        Você poderá alterar o endereço depois em Perfil → Endereço de entrega.
      </p>
    </div>
  )
}

export type { AddressFormProps }
