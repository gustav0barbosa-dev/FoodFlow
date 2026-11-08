import { beforeEach } from 'vitest'
import { useCartStore } from '@/store/cartStore'
import { useOrdersStore } from '@/store/ordersStore'
import { useFavoritesStore } from '@/store/favoritesStore'
import { usePreferencesStore } from '@/store/preferencesStore'

beforeEach(() => {
  localStorage.clear()
  useCartStore.setState({ lines: [] })
  useOrdersStore.setState({ orders: [] })
  useFavoritesStore.setState({ favoriteIds: [] })
  usePreferencesStore.setState({ preferences: [] })
})
