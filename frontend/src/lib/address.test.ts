import { describe, expect, it } from 'vitest'
import {
  EMPTY_ADDRESS,
  formatAddress,
  hasAddressErrors,
  validateAddress,
  type AddressFields,
} from '@/lib/address'

const validAddress: AddressFields = {
  cep: '06110-000',
  street: 'Av. dos Autonomistas',
  number: '1400',
  complement: 'Apto 12',
  neighborhood: 'Centro',
  city: 'Osasco',
  state: 'SP',
}

describe('endereço', () => {
  it('formata o endereço completo', () => {
    expect(formatAddress(validAddress)).toBe(
      'Av. dos Autonomistas, 1400 - Apto 12 - Centro - Osasco - SP'
    )
  })

  it('valida os campos obrigatórios', () => {
    const errors = validateAddress(EMPTY_ADDRESS)

    expect(hasAddressErrors(errors)).toBe(true)
    expect(errors.cep).toBe('Informe o CEP')
    expect(errors.street).toBe('Informe a rua')
    expect(errors.number).toBe('Informe o número')
    expect(errors.state).toBe('Informe o estado')
  })

  it('aceita um endereço completo', () => {
    expect(validateAddress(validAddress)).toEqual({})
  })

  it('permite finalizar só com coordenadas quando nada foi digitado', () => {
    expect(validateAddress(EMPTY_ADDRESS, { allowCoordinatesOnly: true })).toEqual(
      {}
    )
  })

  it('não aceita apenas coordenadas se o endereço estiver parcialmente preenchido', () => {
    const errors = validateAddress(
      { ...EMPTY_ADDRESS, street: 'Av. dos Autonomistas' },
      { allowCoordinatesOnly: true }
    )

    expect(errors.cep).toBe('Informe o CEP')
    expect(errors.number).toBe('Informe o número')
  })
})
