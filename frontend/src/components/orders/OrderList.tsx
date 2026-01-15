import { useOrders } from '../../hooks/useOrders'
import { useUIStore } from '../../stores/uiStore'
import { OrderCard } from './OrderCard'
import { OrderCardSkeleton } from '../ui/skeleton'

export function OrderList() {
  const { data, isLoading, error } = useOrders({ status: 'unfulfilled' })
  const selectedOrderId = useUIStore((s) => s.selectedOrderId)
  const selectOrder = useUIStore((s) => s.selectOrder)
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen)

  const handleSelectOrder = (orderId: string) => {
    selectOrder(orderId)
    // Close sidebar on mobile after selection
    if (window.innerWidth < 768) {
      setSidebarOpen(false)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <OrderCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-text-dim py-8 px-4">
        <p>Failed to load orders</p>
        <p className="text-xs mt-1">Please try again later</p>
      </div>
    )
  }

  const orders = data?.orders ?? []

  if (orders.length === 0) {
    return (
      <div className="text-center text-text-dim py-8 px-4">
        <p>No unfulfilled orders</p>
      </div>
    )
  }

  return (
    <div>
      {orders.map((order) => (
        <OrderCard
          key={order.id}
          order={order}
          isSelected={selectedOrderId === order.id}
          onClick={() => handleSelectOrder(order.id)}
        />
      ))}
    </div>
  )
}
