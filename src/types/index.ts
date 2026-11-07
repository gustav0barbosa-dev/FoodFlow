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
  isRecommended: boolean
  menu: MenuItem[]
  reviews: Review[]
}

export interface CartLine {
  restaurantId: string
  restaurantName: string
  item: MenuItem
  quantity: number
}