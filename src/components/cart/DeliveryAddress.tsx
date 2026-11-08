import { useState, type FormEvent } from 'react'
import { MapPin, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { useAddressStore } from '@/store/addressStore'

const MIN_ADDRESS_LENGTH = 5

export function DeliveryAddress() {
  const address = useAddressStore((s) => s.address)
  const setAddress = useAddressStore((s) => s.setAddress)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(address)
  const [error, setError] = useState<string | null>(null)

  const startEditing = () => {
    setDraft(address)
    setError(null)
    setEditing(true)
  }

  const handleSave = (event: FormEvent) => {
    event.preventDefault()
    const value = draft.trim()

    if (value.length < MIN_ADDRESS_LENGTH) {
      setError(`Informe um endereço com pelo menos ${MIN_ADDRESS_LENGTH} caracteres.`)
      return
    }

    setAddress(value)
    setEditing(false)
    toast.success('Endereço de entrega atualizado')
  }

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <div className="flex items-start justify-between gap-2">
        <h2 className="font-display font-semibold text-ink flex items-center gap-1.5">
          <MapPin size={16} className="text-primary" />
          Endereço de entrega
        </h2>
        {!editing && (
          <button
            type="button"
            onClick={startEditing}
            aria-label="Alterar endereço de entrega"
            className="flex items-center gap-1 text-xs font-medium text-primary px-2 py-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <Pencil size={12} />
            Alterar
          </button>
        )}
      </div>

      {editing ? (
        <form onSubmit={handleSave} className="mt-3 space-y-2">
          <label htmlFor="delivery-address" className="sr-only">
            Endereço de entrega
          </label>
          <input
            id="delivery-address"
            autoFocus
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value)
              if (error) setError(null)
            }}
            placeholder="Rua, número, complemento — cidade"
            className="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-ink placeholder:text-ink-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          {error && (
            <p role="alert" className="text-xs text-primary-dark">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={draft.trim().length === 0}
              className="flex-1 bg-primary text-white rounded-xl py-2 text-sm font-semibold hover:bg-primary-dark disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              Salvar endereço
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="px-3 py-2 text-sm font-medium text-ink-soft rounded-xl hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <p className="mt-2 text-sm text-ink">{address}</p>
      )}
    </section>
  )
}
