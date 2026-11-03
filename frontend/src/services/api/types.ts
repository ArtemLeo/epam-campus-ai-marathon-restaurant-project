/**
 * Response/request shapes of the Python backend (backend/src/lambdas/api_handler).
 * Field names follow the original Green & Tasty API, including its PascalCase guest-invite payloads.
 */
import type { CatalogLocale, DishListResponse, DishTranslations } from '@/models/dishes/dish-list-response.model'

export type { DishTranslations } from '@/models/dishes/dish-list-response.model'
export type LocationTranslations = Partial<Record<CatalogLocale, { description?: string }>>

export type Dish = DishListResponse

export type DishTypeName = 'Appetizer' | 'MainCourse' | 'Dessert'
export type DishSortName = 'PriceAscending' | 'PriceDescending' | 'PopularityAscending' | 'PopularityDescending'

export interface Location {
  id: string
  address: string
  description: string
  translations?: LocationTranslations
  /** Number of tables at the location. */
  totalCapacity: number
  /** "65%" */
  averageOccupancy: string
  imageUrl: string | null
  /** Average of all feedback ratings, 0 when there is none. */
  rating: number
}

export interface LocationRequest {
  address: string
  description: string
  translations?: LocationTranslations
  totalCapacity?: number
  averageOccupancy: string
  imageBase64?: string | null
  rating?: number
}

export interface DishRequest {
  name: string
  description: string
  translations?: DishTranslations
  dishType: DishTypeName
  price: number
  weight: string
  calories: string
  proteins: string
  fats: string
  carbohydrates: string
  vitamins: string
  state: 'Available' | 'OnStop' | 'OutOfStock'
  imageBase64?: string | null
  locationIds: string[]
}

export interface Table {
  id: string
  locationId: string
  capacity: number
  tableNumber: number
}

export interface TimeSlot {
  start: string
  end: string
}

/** 0 Reserved · 1 Cancelled · 2 InProgress · 3 Completed */
export type ReservationStatusCode = 0 | 1 | 2 | 3

export interface Reservation {
  id: string
  tableId: string
  locationId: string
  startTime: string
  endTime: string
  guestCount: number
  status: ReservationStatusCode
  customerId: string | null
  waiterId: string
  locationAddress: string
  restaurantName: string
  /** The waiter confirmed the pre-order (order status Submitted). */
  hasSubmittedPreOrder: boolean
  /** A guest invite link can be shared (2+ guests and the group pre-order is still open). */
  guestInviteLinkAvailable: boolean
}

export interface CreateReservationRequest {
  tableId: string
  startTime: string
  endTime: string
  guestCount: number
  /** Waiter only: book on behalf of a registered customer. */
  customerEmail?: string | null
}

export interface EditReservationRequest {
  reservationId: string
  startTime: string
  endTime: string
  guestCount: number
}

/** 0 Pending · 1 Confirmed · 2 Canceled (set by the waiter per dish) */
export type OrderItemState = 0 | 1 | 2

export interface OrderItem {
  dish: Dish
  quantity: number
  state: OrderItemState
}

/** 0 Created · 1 Submitted (confirmed by the waiter) · 2 Cancelled · 3 SubmittedByCustomer */
export type OrderStatusCode = 0 | 1 | 2 | 3

export interface Order {
  orderId: string
  reservationId: string
  reservationAddress: string
  /** "Aug 07, 2026, 7:00 PM - 8:30 PM" */
  reservationTime: string
  reservationStartTime: string | null
  reservationEndTime: string | null
  canEdit: boolean
  editDisabledReason: string | null
  groupSubmitted: boolean
  orderItems: OrderItem[]
  status: OrderStatusCode
}

export interface OrderLine {
  dishId: string
  quantity: number
}

/** 0 Service · 1 CuisineExperience */
export type FeedbackTypeCode = 0 | 1

export interface Feedback {
  reservationId: string
  locationId: string
  userId: string | null
  comment: string | null
  rating: number
  createdAt: string
  type: FeedbackTypeCode
  username: string | null
}

export interface FeedbackPage {
  items: Feedback[]
  totalPages: number
  currentPage: number
}

export interface ReservationFeedback {
  service: Feedback | null
  cuisineExperience: Feedback | null
}

export interface FeedbackRequest {
  token?: string
  reservationId: string
  rating: number
  type: FeedbackTypeCode
  comment?: string | null
}

export type FeedbackSort = 'TopRatedFirst' | 'LowRatedFirst' | 'NewestFirst' | 'OldestFirst'

export interface Notification {
  id: string
  message: string
  orderId: string | null
  reservationId: string | null
  createdAt: string
  isRead: boolean
  kind?: 'NewOrder' | 'GroupOrder'
  tableNumber?: number
  guestCount?: number
  startTime?: string
  locationAddress?: string
  dishes?: { id: string; name: string; quantity: number; translations?: DishTranslations }[]
}

export interface User {
  id: string
  firstName: string
  lastName: string
  email: string
  role: 'Admin' | 'Waiter' | 'Customer'
}

export interface Waiter {
  userId: string
  email: string
  firstName: string
  lastName: string
  locationId: string
}

export interface SignInResponse {
  message: string
  idToken: string
  accessToken: string
}

export interface RegisterRequest {
  firstName: string
  lastName: string
  email: string
  password: string
  confirmPassword: string
}

/** 0 Service (per waiter) · 1 Sales (per location) */
export type ReportTypeCode = 0 | 1

export interface ReportRow {
  reportType: ReportTypeCode
  startDate: string
  endDate: string
  userId: string
  locationId: string
  locationName: string
  // Service report
  waiterId?: string
  waiterName?: string
  waiterEmail?: string
  workingHours?: number
  totalOrders: number
  avgServiceFeedback?: number
  minServiceFeedback?: number
  deltaAvgServiceFeedback?: number
  deltaTotalOrders?: number
  // Sales report
  revenue?: number
  avgCuisineFeedback?: number
  minCuisineFeedback?: number
  deltaAvgCuisineFeedback?: number
  deltaRevenue?: number
}

export interface ReportHistoryItem {
  startDate: string
  endDate: string
  userId: string
  locationId: string
  locationName: string
  reportType: ReportTypeCode
}

export type ReportFormat = 'csv' | 'excel' | 'pdf'

export interface ReportQuery {
  locale?: CatalogLocale
  type: ReportTypeCode
  locationId: string
  /** YYYY-MM-DD */
  startDate: string
  /** YYYY-MM-DD */
  endDate: string
}

export interface GuestMenuDish {
  id: string
  name: string
  description: string
  translations?: DishTranslations
  price: number
  weight: string
  calories: string
  proteins: string
  fats: string
  carbohydrates: string
  vitamins: string
  imageUrl: string | null
  state: 'Available' | 'OnStop' | 'OutOfStock'
  selectable: boolean
}

export interface GuestMenu {
  dishes: Partial<Record<DishTypeName, GuestMenuDish[]>>
}

export interface GuestSessionCreated {
  SessionId: string
  SessionToken: string
}

export interface GuestSessionInfo {
  name: string
  items: { dish: Dish; quantity: number }[]
  total: number
  isSubmitted: boolean
}

/** 400 responses of the guest flow carry one of these codes. */
export type GuestErrorCode = 'GroupReservationExpired' | 'GroupReservationSubmitted' | 'GuestLimitExceeded' | 'GuestSessionExpired'
