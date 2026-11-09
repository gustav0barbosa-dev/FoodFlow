export interface MenuItem {
  id: string
  name: string
  description: string
  price: number
  image: string
}

export interface Review {
  id: string
  userName: string
  rating: number
  date: string
  comment: string
  userId?: string
}

export const DIETARY_PREFERENCES = [
  'Vegano',
  'Vegetariano',
  'Sem glúten',
  'Sem lactose',
] as const

export type DietaryPreference = (typeof DIETARY_PREFERENCES)[number]

export interface Restaurant {
  id: string
  name: string
  category: string
  image: string
  rating: number
  reviewCount: number
  distanceKm: number
  deliveryFee: number
  deliveryTimeMin: number
  deliveryTimeMax: number
  address: string
  phone: string
  tags: string[]
  dietaryTags: DietaryPreference[]
  isRecommended: boolean
  menu: MenuItem[]
  reviews: Review[]
  hours: string
  paymentMethods: string[]
}

export interface CartLine {
  restaurantId: string
  restaurantName: string
  item: MenuItem
  quantity: number
}