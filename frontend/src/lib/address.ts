import { onlyDigits } from '@/lib/validation'

export interface AddressFields {
  cep: string
  street: string
  number: string
  complement: string
  neighborhood: string
  city: string
  state: string
}

export type AddressField = keyof AddressFields

export type AddressErrors = Partial<Record<AddressField, string>>

export type AddressMode = 'manual' | 'location'

export interface Coordinates {
  lat: number
  lon: number
}

export const EMPTY_ADDRESS: AddressFields = {
  cep: '',
  street: '',
  number: '',
  complement: '',
  neighborhood: '',
  city: '',
  state: '',
}

/** Formata o endereço para exibição e para o endereço de entrega do carrinho. */
export function formatAddress(address: AddressFields) {
  const streetLine = [address.street.trim(), address.number.trim()]
    .filter(Boolean)
    .join(', ')

  const neighborhoodLine = [address.complement.trim(), address.neighborhood.trim()]
    .filter(Boolean)
    .join(' - ')

  const cityLine = [address.city.trim(), address.state.trim()]
    .filter(Boolean)
    .join(' - ')

  return [streetLine, neighborhoodLine, cityLine].filter(Boolean).join(' - ')
}

export function addressLocationLabel(address: AddressFields) {
  return (
    [address.neighborhood.trim(), address.city.trim()]
      .filter(Boolean)
      .join(', ') || 'Minha localização'
  )
}

/**
 * Valida os campos do endereço.
 *
 * `allowCoordinatesOnly` permite finalizar quando a pessoa usou a localização
 * atual e o reverse geocoding não preencheu nenhum campo textual.
 */
export function validateAddress(
  address: AddressFields,
  { allowCoordinatesOnly = false }: { allowCoordinatesOnly?: boolean } = {}
): AddressErrors {
  const hasAnyText = Object.values(address).some((value) => value.trim().length > 0)

  if (allowCoordinatesOnly && !hasAnyText) return {}

  const errors: AddressErrors = {}
  const cepDigits = onlyDigits(address.cep)

  if (!cepDigits) {
    errors.cep = 'Informe o CEP'
  } else if (cepDigits.length !== 8) {
    errors.cep = 'CEP inválido. Use 8 dígitos.'
  }

  if (!address.street.trim()) {
    errors.street = 'Informe a rua'
  } else if (address.street.trim().length < 3) {
    errors.street = 'Rua muito curta'
  }

  if (!address.number.trim()) {
    errors.number = 'Informe o número'
  }

  if (!address.neighborhood.trim()) {
    errors.neighborhood = 'Informe o bairro'
  }

  if (!address.city.trim()) {
    errors.city = 'Informe a cidade'
  }

  if (!address.state.trim()) {
    errors.state = 'Informe o estado'
  } else if (!/^[A-Za-z]{2}$/.test(address.state.trim())) {
    errors.state = 'Use a sigla (ex.: SP)'
  }

  return errors
}

export function hasAddressErrors(errors: AddressErrors) {
  return Object.keys(errors).length > 0
}
