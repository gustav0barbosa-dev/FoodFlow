import { afterEach, beforeEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import { useCartStore } from '@/store/cartStore'
import { useOrdersStore } from '@/store/ordersStore'
import { useFavoritesStore } from '@/store/favoritesStore'
import { usePreferencesStore } from '@/store/preferencesStore'
import { DEFAULT_ADDRESS, useAddressStore } from '@/store/addressStore'
import { useEventsStore } from '@/store/eventsStore'
import { useEventFiltersStore } from '@/store/eventFiltersStore'
import { DEFAULT_RESTAURANT_SORT, useSortStore } from '@/store/sortStore'
import { DEFAULT_HOME_CATEGORY, DEFAULT_HOME_FILTER, useHomeFiltersStore } from '@/store/homeFiltersStore'

afterEach(() => {
  cleanup()
})

beforeEach(() => {
  localStorage.clear()
  useCartStore.setState({ lines: [] })
  useOrdersStore.setState({ orders: [] })
  useFavoritesStore.setState({ favoriteIds: [] })
  usePreferencesStore.setState({ preferences: [] })
  useAddressStore.setState({ address: DEFAULT_ADDRESS })
  useEventsStore.setState({ events: [] })
  useEventFiltersStore.setState({ type: 'all', period: 'all' })
  useSortStore.setState({ sort: DEFAULT_RESTAURANT_SORT })
  useHomeFiltersStore.setState({
    filter: DEFAULT_HOME_FILTER,
    category: DEFAULT_HOME_CATEGORY,
  })
})
