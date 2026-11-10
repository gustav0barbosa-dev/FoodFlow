import { onlyDigits } from '@/lib/validation'

export type CepLookupErrorCode = 'invalid' | 'not_found' | 'network'

export class CepLookupError extends Error {
  code: CepLookupErrorCode

  constructor(code: CepLookupErrorCode, message: string) {
    super(message)
    this.name = 'CepLookupError'
    this.code = code
    Object.setPrototypeOf(this, CepLookupError.prototype)
  }
}

export interface CepAddress {
  street: string
  complement: string
  neighborhood: string
  city: string
  state: string
}

interface ViaCepResponse {
  erro?: boolean | string
  logradouro?: string
  complemento?: string
  bairro?: string
  localidade?: string
  uf?: string
}

function read(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

/** Busca o endereço no ViaCEP. Serviço público externo (CORS habilitado). */
export async function fetchAddressByCep(
  cep: string,
  signal?: AbortSignal
): Promise<CepAddress> {
  const digits = onlyDigits(cep)

  if (digits.length !== 8) {
    throw new CepLookupError('invalid', 'Informe um CEP com 8 dígitos')
  }

  let response: Response

  try {
    response = await fetch(`https://viacep.com.br/ws/${digits}/json/`, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new CepLookupError('network', 'Não foi possível consultar o CEP')
  }

  if (!response.ok) {
    throw new CepLookupError('network', 'Não foi possível consultar o CEP')
  }

  let data: ViaCepResponse

  try {
    data = (await response.json()) as ViaCepResponse
  } catch {
    throw new CepLookupError('network', 'Resposta inválida do ViaCEP')
  }

  if (data.erro) {
    throw new CepLookupError('not_found', 'CEP não encontrado')
  }

  return {
    street: read(data.logradouro),
    complement: read(data.complemento),
    neighborhood: read(data.bairro),
    city: read(data.localidade),
    state: read(data.uf).toUpperCase(),
  }
}
