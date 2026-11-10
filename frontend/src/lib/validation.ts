/** Validações e máscaras dos formulários de conta. */

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/i

export function onlyDigits(value: string) {
  return value.replace(/\D/g, '')
}

/** Máscara de telefone: (XX) XXXXX-XXXX (celular) ou (XX) XXXX-XXXX (fixo). */
export function formatPhone(value: string) {
  const digits = onlyDigits(value).slice(0, 11)

  if (digits.length === 0) return ''
  if (digits.length <= 2) return `(${digits}`

  const ddd = digits.slice(0, 2)
  const number = digits.slice(2)

  if (number.length <= 4) return `(${ddd}) ${number}`

  const firstPartLength = digits.length > 10 ? 5 : 4
  const firstPart = number.slice(0, firstPartLength)
  const secondPart = number.slice(firstPartLength)

  return `(${ddd}) ${firstPart}${secondPart ? `-${secondPart}` : ''}`
}

/** Máscara de CEP: XXXXX-XXX. */
export function formatCep(value: string) {
  const digits = onlyDigits(value).slice(0, 8)
  if (digits.length <= 5) return digits
  return `${digits.slice(0, 5)}-${digits.slice(5)}`
}

export function validateEmail(email: string): string | null {
  const trimmed = email.trim()

  if (!trimmed) return 'Informe seu e-mail'
  if (!EMAIL_PATTERN.test(trimmed)) return 'E-mail inválido'

  return null
}

export function validatePassword(password: string): string | null {
  if (!password) return 'Informe uma senha'
  if (password.length < 8) return 'Senha muito curta (mínimo de 8 caracteres)'
  if (password.length > 72) return 'Senha muito longa (máximo de 72 caracteres)'

  return null
}

export function validatePhone(phone: string): string | null {
  const digits = onlyDigits(phone)

  if (!digits) return 'Informe seu telefone'
  if (digits.length < 10 || digits.length > 11) {
    return 'Telefone inválido. Use DDD + número.'
  }
  if (digits.length === 11 && digits[2] !== '9') {
    return 'Celular inválido. O número deve começar com 9 após o DDD.'
  }

  return null
}
