import type { Restaurant } from '@/types'

// TODO: expandir para 12 restaurantes (ver prompt do Lovable para lista sugerida)
export const restaurants: Restaurant[] = [
  {
    id: 'r1',
    name: 'Sabor da Vila',
    category: 'Brasileira',
    image: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=600&h=400&fit=crop',
    rating: 4.8,
    reviewCount: 312,
    distanceKm: 1.2,
    deliveryFee: 5.99,
    deliveryTimeMin: 25,
    deliveryTimeMax: 35,
    address: 'Av. dos Autonomistas, 1400 — Osasco, SP',
    phone: '+5511999999999',
    tags: ['Promoção', 'Frete grátis'],
    isRecommended: true,
    menu: [
      { id: 'm1', name: 'Feijoada Completa', description: 'Serve 2 pessoas', price: 42.9, image: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=300&h=300&fit=crop' },
    ],
    reviews: [
      { id: 'rv1', userName: 'Carlos M.', rating: 5, date: '2025-10-12', comment: 'Comida deliciosa e entrega rápida!' },
    ],
  },
  {
    id: 'r2',
    name: 'Verde Vivo — Saudável',
    category: 'Saudável',
    image: 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=600&h=400&fit=crop',
    rating: 4.7,
    reviewCount: 154,
    distanceKm: 0.8,
    deliveryFee: 0,
    deliveryTimeMin: 20,
    deliveryTimeMax: 30,
    address: 'R. Antônio Agu, 500 — Osasco, SP',
    phone: '+5511988888888',
    tags: ['Vegano', 'Frete grátis'],
    isRecommended: true,
    menu: [
      { id: 'm2', name: 'Bowl Proteico', description: 'Quinoa, grão-de-bico e legumes', price: 32.5, image: 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=300&h=300&fit=crop' },
    ],
    reviews: [
      { id: 'rv2', userName: 'Marina S.', rating: 5, date: '2025-10-08', comment: 'Opções veganas incríveis!' },
    ],
  },
  // TODO: adicionar os outros 10 restaurantes
]

export const categories = [
  { id: 'c1', name: 'Pizza', emoji: '🍕' },
  { id: 'c2', name: 'Hambúrguer', emoji: '🍔' },
  { id: 'c3', name: 'Japonês', emoji: '🍣' },
  { id: 'c4', name: 'Brasileira', emoji: '🍛' },
  { id: 'c5', name: 'Saudável', emoji: '🥗' },
  { id: 'c6', name: 'Doces', emoji: '🍰' },
  { id: 'c7', name: 'Bebidas', emoji: '🥤' },
  { id: 'c8', name: 'Árabe', emoji: '🥙' },
]

export const currentUser = {
  name: 'Ana Silva',
  email: 'ana@email.com',
  location: 'Osasco, SP',
}