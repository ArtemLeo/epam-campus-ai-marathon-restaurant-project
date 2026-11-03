export interface ReservationCustomer {
  id: string
  tableId: string
  startTime: string
  endTime: string
  guestCount: number
  status: ReservationStatusCustomer
  restaurantName: string
  locationAddress: string
  feedback?: { rating: number; comment?: string }
  tableName?: string
  customerId?: string
  waiterId: string
  hasSubmittedPreOrder?: boolean
  guestInviteLinkAvailable?: boolean
  preOrder?: { orderId: string; orderItems: unknown[] }
  preOrders?: { orderId: string; orderItems: unknown[] }[]
  createdByName?: string
  createdByRole?: 'Customer' | 'Waiter'
}

export enum ReservationStatusCustomer {
  Reserved = 0,
  Cancelled = 1,
  InProgress = 2,
  Finished = 3,
}

export type ReservationStatusKey = 'reserved' | 'cancelled' | 'in-progress' | 'finished'

/** The API sends the status as the enum number; older payloads used its name. Normalise both. */
export function reservationStatusKey(status: ReservationStatusCustomer | string | null | undefined): ReservationStatusKey | null {
  switch (typeof status === 'string' ? status.toLowerCase() : status) {
    case ReservationStatusCustomer.Reserved:
    case 'reserved':
      return 'reserved'
    case ReservationStatusCustomer.Cancelled:
    case 'cancelled':
      return 'cancelled'
    case ReservationStatusCustomer.InProgress:
    case 'inprogress':
    case 'in progress':
      return 'in-progress'
    case ReservationStatusCustomer.Finished:
    case 'finished':
    case 'completed':
      return 'finished'
    default:
      return null
  }
}
