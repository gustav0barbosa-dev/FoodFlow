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
  dietaryTags: string[]
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

export interface OrderItem {
  id: string
  name: string
  price: number
  quantity: number
}

export interface Order {
  id: string
  restaurantNames: string[]
  items: OrderItem[]
  itemCount: number
  subtotal: number
  deliveryFee: number
  total: number
  address?: string
  status: 'Em preparo' | 'Saiu para entrega' | 'Entregue'
  createdAt: string
}

export interface NewOrderInput {
  restaurantNames: string[]
  items: OrderItem[]
  subtotal: number
  deliveryFee: number
  total: number
  address: string
}

export type DietaryPreference =
  | 'Vegano'
  | 'Vegetariano'
  | 'Sem glúten'
  | 'Sem lactose'

export type Turno = 'manha' | 'tarde' | 'noite' | 'madrugada'

export type ABGroup = 'personalized' | 'distance' | ''

export interface AnalyticsEvent {
  id: string
  type: string
  payload: Record<string, string | number | string[]>
  createdAt: string
}

export const DIETARY_PREFERENCES: DietaryPreference[] = [
  'Vegano',
  'Vegetariano',
  'Sem glúten',
  'Sem lactose',
]

export type EventType =
  | 'restaurant_card_clicked'
  | 'restaurant_opened'
  | 'add_to_cart'
  | 'order_completed'
  | 'preferences_updated'
  | 'search_performed'
  | 'favorite_toggled'
  | 'order_status_updated'
  | 'review_submitted'
