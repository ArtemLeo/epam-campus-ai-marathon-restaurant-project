import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ordersApi, type Dish, type Order, type OrderLine } from '@/services/api'
import {
  isDraft,
  isSent,
  linesWithAddedDish,
  linesWithoutDish,
  linesWithQuantity,
} from '@/components/cart/cart-math'

/**
 * Customer pre-order cart (port of the Angular CartComponent + PreOrdersService).
 * One active order per reservation: the first dish creates it, later changes replace its lines,
 * and removing the last dish cancels it.
 */
export const useCartStore = defineStore('cart', () => {
  const orders = ref<Order[]>([])
  const isOpen = ref(false)
  const loading = ref(false)
  const busy = ref(false)
  /** Order whose "Pre-order Submitted!" dialog is shown. */
  const submittedOrderId = ref<string | null>(null)
  /** Order waiting for the "Cancel Order" confirmation. */
  const cancelOrderId = ref<string | null>(null)

  const draftOrders = computed(() => orders.value.filter(isDraft))
  const sentOrders = computed(() => orders.value.filter(isSent))
  /** Dishes waiting in not-submitted pre-orders (badge on the cart button). */
  const draftItemCount = computed(() =>
    draftOrders.value.reduce((sum, order) => sum + order.orderItems.reduce((n, item) => n + item.quantity, 0), 0),
  )
  const submittedOrder = computed(() => orders.value.find((order) => order.orderId === submittedOrderId.value))

  let revision = 0
  function reset(): void {
    revision++
    orders.value = []
    loading.value = false
    busy.value = false
    close()
  }

  async function load(): Promise<void> {
    const requestRevision = revision
    loading.value = true
    try {
      const result = await ordersApi.list()
      if (requestRevision === revision) orders.value = result
    } catch {
      if (requestRevision === revision) orders.value = []
    } finally {
      if (requestRevision === revision) loading.value = false
    }
  }

  function open(): void {
    isOpen.value = true
    void load()
  }

  function close(): void {
    isOpen.value = false
    submittedOrderId.value = null
    cancelOrderId.value = null
  }

  function toggle(): void {
    if (isOpen.value) close()
    else open()
  }

  function find(orderId: string): Order | undefined {
    return orders.value.find((order) => order.orderId === orderId)
  }

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    busy.value = true
    try {
      await action()
      return true
    } catch {
      return false // the API client already showed the error toast
    } finally {
      busy.value = false
      await load()
    }
  }

  async function saveLines(order: Order, lines: OrderLine[]): Promise<boolean> {
    return run(() =>
      lines.length ? ordersApi.edit(order.reservationId, lines) : ordersApi.cancel(order.reservationId),
    )
  }

  /** Add a dish to the reservation's pre-order, creating the order on the first dish. */
  async function addDish(reservationId: string, dish: Dish, quantity = 1): Promise<boolean> {
    let current: Order[]
    try {
      current = await ordersApi.list()
    } catch {
      return false
    }
    const order = current.find((item) => item.reservationId === reservationId)
    const lines = linesWithAddedDish(order, dish, quantity)
    return run(() => (order ? ordersApi.edit(reservationId, lines) : ordersApi.create(reservationId, lines)))
  }

  async function updateQuantity(orderId: string, dishId: string, quantity: number): Promise<void> {
    const order = find(orderId)
    if (!order || quantity < 1) return
    await saveLines(order, linesWithQuantity(order, dishId, quantity))
  }

  async function removeDish(orderId: string, dishId: string): Promise<void> {
    const order = find(orderId)
    if (order) await saveLines(order, linesWithoutDish(order, dishId))
  }

  async function submit(orderId: string): Promise<void> {
    const order = find(orderId)
    if (order && (await run(() => ordersApi.submit(order.reservationId)))) submittedOrderId.value = orderId
  }

  /** "Edit Pre-order": move a submitted pre-order back to the draft list. */
  async function edit(orderId: string): Promise<void> {
    const order = find(orderId)
    submittedOrderId.value = null
    if (order) await run(() => ordersApi.unsubmit(order.reservationId))
  }

  async function cancel(orderId: string): Promise<void> {
    const order = find(orderId)
    if (order && (await run(() => ordersApi.cancel(order.reservationId)))) cancelOrderId.value = null
  }

  return {
    reset,
    orders,
    isOpen,
    loading,
    busy,
    submittedOrderId,
    cancelOrderId,
    draftOrders,
    sentOrders,
    draftItemCount,
    submittedOrder,
    load,
    open,
    close,
    toggle,
    addDish,
    updateQuantity,
    removeDish,
    submit,
    edit,
    cancel,
  }
})
