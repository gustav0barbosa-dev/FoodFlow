import { useEffect } from 'react'
import { useCatalogStore } from '@/store/catalogStore'

/** Carrega o catálogo uma única vez e expõe o estado para as páginas. */
export function useCatalog() {
  const restaurants = useCatalogStore((state) => state.restaurants)
  const source = useCatalogStore((state) => state.source)
  const loading = useCatalogStore((state) => state.loading)
  const error = useCatalogStore((state) => state.error)
  const loaded = useCatalogStore((state) => state.loaded)
  const load = useCatalogStore((state) => state.load)

  useEffect(() => {
    void load()
  }, [load])

  return { restaurants, source, loading, error, loaded, load }
}
