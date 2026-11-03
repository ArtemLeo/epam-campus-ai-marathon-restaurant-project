import type { Dish, Order, OrderItem, OrderLine } from '@/services/api'
import { formatDate, formatTime } from '@/utils/formatters'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'

/** Order items as the `{ dishId, quantity }` lines the API expects. */
export function orderLines(items: readonly Pick<OrderItem, 'dish' | 'quantity'>[]): OrderLine[] {
  return items.map((item) => ({ dishId: item.dish.id, quantity: item.quantity }))
}

/** Lines after adding `quantity` of a dish (merged with an existing line of the same dish). */
export function linesWithAddedDish(order: Order | undefined, dish: Pick<Dish, 'id'>, quantity: number): OrderLine[] {
  const lines = order ? orderLines(order.orderItems) : []
  const existing = lines.find((line) => line.dishId === dish.id)
  if (existing) existing.quantity += quantity
  else lines.push({ dishId: dish.id, quantity })
  return lines
}

/** Lines with a new quantity for one dish; quantities below 1 are ignored (use removal instead). */
export function linesWithQuantity(order: Order, dishId: string, quantity: number): OrderLine[] {
  return orderLines(order.orderItems).map((line) =>
    line.dishId === dishId ? { ...line, quantity: Math.max(1, quantity) } : line,
  )
}

export function linesWithoutDish(order: Order, dishId: string): OrderLine[] {
  return orderLines(order.orderItems).filter((line) => line.dishId !== dishId)
}

/** Sum of price × quantity; dishes rejected by the waiter (state 2) are not charged. */
export function orderTotal(order: Pick<Order, 'orderItems'>, excludeRejected = false): number {
  return order.orderItems
    .filter((item) => !excludeRejected || item.state !== 2)
    .reduce((total, item) => total + item.dish.price * item.quantity, 0)
}

/** Created (0) orders are still a draft; Submitted (1) and SubmittedByCustomer (3) were sent. */
export const isDraft = (order: Pick<Order, 'status'>): boolean => order.status === 0
export const isSent = (order: Pick<Order, 'status'>): boolean => order.status === 1 || order.status === 3

export const ITEM_STATE_LABELS: Record<number, string> = { 0: 'Pending', 1: 'Confirmed', 2: 'Rejected' }

/** Prefer machine-readable times so changing the interface language also changes reservation dates. */
export function orderReservationTime(order: Pick<Order, 'reservationStartTime' | 'reservationEndTime' | 'reservationTime'>): string {
  if (!order.reservationStartTime) return order.reservationTime
  const end = order.reservationEndTime ? ` – ${formatTime(order.reservationEndTime)}` : ''
  return `${formatDate(order.reservationStartTime)}${end} (${RESTAURANT_TIMEZONE})`
}
