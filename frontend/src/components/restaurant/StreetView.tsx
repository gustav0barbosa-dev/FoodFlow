import { useEffect, useState } from 'react'
import { getStreetViewMetadata, streetViewImageUrl } from '@/lib/api'

interface StreetViewProps {
  latitude: number
  longitude: number
  name: string
}

/**
 * Panorama opcional da Google Street View.
 *
 * A chave da API nunca chega ao navegador: a metadata é consultada e a
 * imagem é carregada pelo proxy do backend. Quando não há cobertura, chave
 * configurada ou ocorre qualquer falha, o componente simplesmente não é
 * renderizado — a tela continua funcionando sem ele.
 */
export function StreetView({ latitude, longitude, name }: StreetViewProps) {
  const [available, setAvailable] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let active = true
    setAvailable(false)
    setLoaded(false)

    getStreetViewMetadata({ lat: latitude, lon: longitude })
      .then((metadata) => {
        if (active) setAvailable(metadata.available)
      })
      .catch(() => {
        // Sem Street View (ou API indisponível) o bloco fica oculto.
        if (active) setAvailable(false)
      })

    return () => {
      active = false
    }
  }, [latitude, longitude])

  if (!available) return null

  return (
    <figure className="mt-3 overflow-hidden rounded-2xl border border-gray-100 bg-surface-muted">
      <div className="relative">
        <img
          src={streetViewImageUrl({ lat: latitude, lon: longitude })}
          alt={`Vista da rua em frente a ${name}`}
          className="h-40 w-full object-cover"
          loading="lazy"
          onLoad={() => setLoaded(true)}
          onError={() => setAvailable(false)}
        />
        {!loaded && (
          <div
            className="absolute inset-0 animate-pulse bg-gray-100"
            aria-hidden="true"
          />
        )}
      </div>
      <figcaption className="px-3 py-1.5 text-[10px] text-ink-soft">
        Imagem © Google Street View
      </figcaption>
    </figure>
  )
}
