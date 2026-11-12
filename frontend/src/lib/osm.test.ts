import { describe, expect, it } from 'vitest'
import {
  categoryLabel,
  filterOsmRestaurants,
  formatOsmAddress,
  osmDetailPath,
  osmKey,
  osmSearchText,
  osmTags,
  sortOsmRestaurants,
} from '@/lib/osm'
import type { OsmRestaurant } from '@/types'

function osm(overrides: Partial<OsmRestaurant> = {}): OsmRestaurant {
  return {
    osm_id: 1,
    osm_type: 'node',
    name: 'Cantina da Praça',
    latitude: -23.55,
    longitude: -46.63,
    category: 'restaurant',
    cuisine: 'italian',
    address: {
      street: 'Rua Teste',
      number: '100',
      city: 'Mogi das Cruzes',
      postcode: null,
    },
    phone: null,
    website: null,
    opening_hours: null,
    osm_url: null,
    dietary_tags: [],
    distance_km: 1.2,
    ...overrides,
  }
}

describe('osm helpers', () => {
  it('monta identificador e rota estáveis por tipo/id', () => {
    expect(osmKey(osm({ osm_type: 'way', osm_id: 42 }))).toBe('way/42')
    expect(osmDetailPath(osm({ osm_type: 'relation', osm_id: 7 }))).toBe(
      '/restaurante/osm/relation/7'
    )
  })

  it('formata endereço ignorando campos ausentes', () => {
    expect(formatOsmAddress(osm().address)).toBe(
      'Rua Teste, 100 · Mogi das Cruzes'
    )
    expect(formatOsmAddress(null)).toBe('')
  })

  it('usa rótulo amigável e mantém categoria desconhecida', () => {
    expect(categoryLabel('cafe')).toBe('Café')
    expect(categoryLabel(null)).toBe('Restaurante')
    expect(categoryLabel('food_court')).toBe('food_court')
  })

  it('inclui dietas no texto de busca e nos rótulos', () => {
    const restaurant = osm({ dietary_tags: ['Vegano', 'Sem glúten'] })

    expect(osmSearchText(restaurant)).toContain('Vegano')
    expect(osmSearchText(restaurant)).toContain('Mogi das Cruzes')
    expect(osmTags(restaurant)).toEqual([
      'Restaurante',
      'italian',
      'Vegano',
      'Sem glúten',
    ])
  })

  it('tolera dietary_tags ausente', () => {
    const restaurant = osm()
    delete (restaurant as Partial<OsmRestaurant>).dietary_tags

    expect(osmTags(restaurant)).toEqual(['Restaurante', 'italian'])
    expect(osmSearchText(restaurant)).toContain('Cantina da Praça')
  })

  it('ordena por distância e usa nome como desempate', () => {
    const far = osm({ osm_id: 1, name: 'B', distance_km: 5 })
    const near = osm({ osm_id: 2, name: 'Z', distance_km: 1 })
    const sameA = osm({ osm_id: 3, name: 'A', distance_km: 1 })
    const missing = osm({ osm_id: 4, name: 'C', distance_km: null })

    const sorted = sortOsmRestaurants([far, near, sameA, missing], 'distance')

    expect(sorted.map((item) => item.osm_id)).toEqual([3, 2, 1, 4])
  })

  it('não inventa avaliação/frete: ordena por nome nesses critérios', () => {
    const items = [
      osm({ osm_id: 1, name: 'Zeta' }),
      osm({ osm_id: 2, name: 'Alfa' }),
    ]

    expect(sortOsmRestaurants(items, 'rating').map((item) => item.name)).toEqual([
      'Alfa',
      'Zeta',
    ])
    expect(
      sortOsmRestaurants(items, 'deliveryFee').map((item) => item.name)
    ).toEqual(['Alfa', 'Zeta'])
  })

  it('mantém a ordem original em "recommended" e não muta a entrada', () => {
    const items = [osm({ osm_id: 1, name: 'B' }), osm({ osm_id: 2, name: 'A' })]

    expect(sortOsmRestaurants(items, 'recommended').map((i) => i.name)).toEqual([
      'B',
      'A',
    ])
    sortOsmRestaurants(items, 'rating')
    expect(items.map((i) => i.name)).toEqual(['B', 'A'])
  })
})

describe('filterOsmRestaurants', () => {
  const items = [
    osm({
      osm_id: 1,
      name: 'Cantina da Praça',
      cuisine: 'italian',
      distance_km: 0.8,
      dietary_tags: [],
    }),
    osm({
      osm_id: 2,
      name: 'Veggie Garden',
      cuisine: 'vegetarian',
      distance_km: 3.4,
      dietary_tags: ['Vegano'],
    }),
    osm({
      osm_id: 3,
      name: 'Bar do Zé',
      category: 'bar',
      cuisine: null,
      distance_km: 12,
      dietary_tags: [],
    }),
  ]

  it('sem filtros devolve tudo na ordem original', () => {
    expect(filterOsmRestaurants(items).map((item) => item.osm_id)).toEqual([
      1, 2, 3,
    ])
  })

  it('busca por nome/culinária/endereço sem diferenciar acentos', () => {
    expect(
      filterOsmRestaurants(items, { query: 'praca' }).map((i) => i.osm_id)
    ).toEqual([1])
    expect(
      filterOsmRestaurants(items, { query: 'vegetarian' }).map((i) => i.osm_id)
    ).toEqual([2])
    expect(
      filterOsmRestaurants(items, { query: 'mogi das cruzes' }).map(
        (i) => i.osm_id
      )
    ).toEqual([1, 2, 3])
  })

  it('filtra por culinária exata', () => {
    expect(
      filterOsmRestaurants(items, { cuisine: 'italian' }).map((i) => i.osm_id)
    ).toEqual([1])
    expect(filterOsmRestaurants(items, { cuisine: 'japanese' })).toEqual([])
  })

  it('filtra por distância máxima, descartando quem não tem distância', () => {
    expect(
      filterOsmRestaurants(items, { maxDistanceKm: 4 }).map((i) => i.osm_id)
    ).toEqual([1, 2])
    expect(
      filterOsmRestaurants(items, { maxDistanceKm: 0.5 }).map((i) => i.osm_id)
    ).toEqual([])
  })

  it('aplica o chip Vegano apenas a quem declara a dieta', () => {
    expect(
      filterOsmRestaurants(items, { chip: 'Vegano' }).map((i) => i.osm_id)
    ).toEqual([2])
  })

  it('aplica chips genéricos sobre os rótulos do OSM', () => {
    expect(
      filterOsmRestaurants(items, { chip: 'Bar' }).map((i) => i.osm_id)
    ).toEqual([3])
    expect(
      filterOsmRestaurants(items, { chip: 'italian' }).map((i) => i.osm_id)
    ).toEqual([1])
  })

  it('combina busca, culinária, distância e ordenação', () => {
    const result = filterOsmRestaurants(items, {
      query: 'garden',
      maxDistanceKm: 5,
      sort: 'distance',
    })

    expect(result.map((item) => item.osm_id)).toEqual([2])
  })

  it('ordena por distância depois de filtrar', () => {
    const result = filterOsmRestaurants(items, {
      chip: 'Todos',
      maxDistanceKm: 5,
      sort: 'distance',
    })

    expect(result.map((item) => item.osm_id)).toEqual([1, 2])
  })
})
