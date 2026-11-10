import { describe, expect, it } from 'vitest'
import { formatCep, formatPhone, validateEmail, validatePassword, validatePhone } from '@/lib/validation'

describe('máscaras', () => {
  it('formata celular com 11 dígitos', () => {
    expect(formatPhone('11999998888')).toBe('(11) 99999-8888')
  })

  it('formata telefone fixo com 10 dígitos', () => {
    expect(formatPhone('1133334444')).toBe('(11) 3333-4444')
  })

  it('formata CEP', () => {
    expect(formatCep('06110000')).toBe('06110-000')
  })
})

describe('validações de conta', () => {
  it('valida e-mail', () => {
    expect(validateEmail('ana@exemplo.com')).toBeNull()
    expect(validateEmail('ana@')).toBe('E-mail inválido')
    expect(validateEmail('')).toBe('Informe seu e-mail')
  })

  it('valida senha com mínimo de 8 caracteres', () => {
    expect(validatePassword('12345678')).toBeNull()
    expect(validatePassword('123')).toBe(
      'Senha muito curta (mínimo de 8 caracteres)'
    )
  })

  it('valida telefone celular e fixo', () => {
    expect(validatePhone('(11) 99999-8888')).toBeNull()
    expect(validatePhone('(11) 3333-4444')).toBeNull()
    expect(validatePhone('119999888')).toBe(
      'Telefone inválido. Use DDD + número.'
    )
  })
})
