import { useEffect } from 'react'
import { useOrdersStore } from '@/store/ordersStore'

const STATUS_CHECK_INTERVAL_MS = 5_000

/**
 * Simulates delivery progression while the app is open and catches up on
 * statuses that became due while it was closed (based on the order createdAt).
 */
export function useOrderAutoAdvance() {
  const syncOrderStatuses = useOrdersStore((s) => s.syncOrderStatuses)

  useEffect(() => {
    syncOrderStatuses()

    const interval = window.setInterval(
      () => syncOrderStatuses(),
      STATUS_CHECK_INTERVAL_MS
    )

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') syncOrderStatuses()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [syncOrderStatuses])
}
