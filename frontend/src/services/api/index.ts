/**
 * Typed wrappers for every backend endpoint (routes.py). Pages call these instead of building URLs.
 * Options such as `skipErrorToast` pass straight through to `apiRequest`.
 */
import { apiDownload, apiRequest, type ApiRequestOptions, type DownloadedFile } from '@/services/http/api-client'
import type { GuestInvite } from '@/models/reservations/guest-invite.model'
import type {
  CreateReservationRequest,
  Dish,
  DishRequest,
  DishSortName,
  DishTypeName,
  EditReservationRequest,
  Feedback,
  FeedbackPage,
  FeedbackRequest,
  FeedbackSort,
  GuestMenu,
  GuestSessionCreated,
  GuestSessionInfo,
  Location,
  LocationRequest,
  Notification,
  Order,
  OrderLine,
  RegisterRequest,
  ReportFormat,
  ReportHistoryItem,
  ReportQuery,
  ReportRow,
  Reservation,
  ReservationFeedback,
  ReservationStatusCode,
  SignInResponse,
  Table,
  TimeSlot,
  User,
  Waiter,
} from './types'

type Options = Omit<ApiRequestOptions, 'method' | 'body'>

const id = encodeURIComponent

function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

const get = <T>(path: string, options?: Options) => apiRequest<T>(path, options)
const post = <T>(path: string, body?: unknown, options?: Options) => apiRequest<T>(path, { ...options, method: 'POST', body: body ?? {} })
const put = <T>(path: string, body: unknown, options?: Options) => apiRequest<T>(path, { ...options, method: 'PUT', body })
const patch = <T>(path: string, body?: unknown, options?: Options) => apiRequest<T>(path, { ...options, method: 'PATCH', body: body ?? {} })
const del = <T>(path: string, body?: unknown, options?: Options) => apiRequest<T>(path, { ...options, method: 'DELETE', body })

export const authApi = {
  register: (body: RegisterRequest, options?: Options) => post<{ message: string; confirmationRequired?: boolean }>('/register', body, options),
  signIn: (email: string, password: string, options?: Options) => post<SignInResponse>('/signin', { email, password }, options),
  confirmRegistration: (email: string, code: string) => post<{ message: string }>('/confirm-registration', { email, code }, { skipErrorToast: true }),
  resendConfirmation: (email: string) => post<{ message: string }>('/resend-confirmation', { email }, { skipErrorToast: true }),
  forgotPassword: (email: string) => post<{ message: string; resetCode?: string }>('/forgot-password', { email }, { skipErrorToast: true }),
  resetPassword: (email: string, code: string, newPassword: string) => post<{ message: string }>('/reset-password', { email, code, newPassword }, { skipErrorToast: true }),
  me: (options?: Options) => get<User>('/me', options),
  updateMe: (firstName: string, lastName: string) => put<{ message: string }>('/me', { firstName, lastName }),
  changePassword: (oldPassword: string, newPassword: string, accessToken: string, options?: Options) =>
    put<{ message: string }>('/me/change-password', { oldPassword, newPassword, accessToken }, options),
  /** `{presignedUrl}` when the very same picture was already stored, otherwise a confirmation string. */
  uploadProfileImage: (base64Image: string) => put<{ presignedUrl: string } | string>('/me/profile-image', { base64Image }),
  /** `{presignedUrl}` or the string "Profile image is not uploaded so far." */
  profileImage: (userId: string, options?: Options) => get<{ presignedUrl: string } | string>(`/users/${id(userId)}/profile-image`, options),
  userName: (userId: string) => get<{ name: string }>(`/users/${id(userId)}/name`),
  /** Waiter: customers whose first name starts with the first word (and last name equals the second). */
  searchUsers: (fullName: string) => get<User[]>(`/users${query({ fullName })}`),
}

export const locationsApi = {
  list: () => get<Location[]>('/locations'),
  get: (locationId: string) => get<Location>(`/locations/${id(locationId)}`),
  create: (body: LocationRequest) => post<Location>('/locations', body),
  update: (locationId: string, body: LocationRequest) => put<Location>(`/locations/${id(locationId)}`, body),
  remove: (locationId: string, force = false) => del<{ message: string }>(`/locations/${id(locationId)}${query({ force: force || undefined })}`),
  /** Specialty dishes of the location. */
  menu: (locationId: string) => get<Dish[]>(`/locations/${id(locationId)}/dishes`),
  removeDish: (locationId: string, dishId: string) => del<{ message: string }>(`/locations/${id(locationId)}/dishes/${id(dishId)}`),
  /** Waiter/Admin: every table of the location. */
  tables: (locationId: string) => get<Table[]>(`/locations/${id(locationId)}/tables/all`),
}

export const dishesApi = {
  list: (filters: { dishType?: DishTypeName; sortBy?: DishSortName; name?: string } = {}) => get<Dish[]>(`/dishes${query(filters)}`),
  popular: () => get<Dish[]>('/dishes/popular'),
  get: (dishId: string) => get<Dish>(`/dishes/${id(dishId)}`),
  create: (body: DishRequest) => post<Dish>('/dishes', body),
  update: (dishId: string, body: DishRequest) => put<Dish>(`/dishes/${id(dishId)}`, body),
  remove: (dishId: string, force = false) => del<{ message: string }>(`/dishes/${id(dishId)}${query({ force: force || undefined })}`),
}

export const tablesApi = {
  /** Tables with a free 90-minute window after `startTime` (ISO) that day. */
  available: (filters: { locationId?: string; capacity?: number; startTime?: string }, options?: Options) =>
    get<Table[]>(`/available-tables${query(filters)}`, options),
  /** Free 90-minute slots (10:00–22:00 restaurant time) starting from `startTime`. */
  timeSlots: (tableId: string, startTime: string, options?: Options) =>
    get<TimeSlot[]>(`/tables/${id(tableId)}/available-time-slots${query({ startTime })}`, options),
  create: (body: { locationId: string; capacity: number; tableNumber: number }) => post<Table>('/tables', body),
  update: (tableId: string, body: { capacity: number; tableNumber: number }) => put<Table>(`/tables/${id(tableId)}`, body),
  remove: (tableId: string) => del<{ message: string }>(`/tables/${id(tableId)}`),
}

export const waitersApi = {
  list: () => get<Waiter[]>('/waiters'),
  add: (email: string, locationId: string) => post<{ message: string }>('/waiters', { email, locationId }),
  remove: (email: string) => del<{ message: string }>('/waiters', { email }),
  location: (userId: string, options?: Options) => get<{ locationId: string }>(`/waiters/${id(userId)}/location`, options),
}

export const reservationsApi = {
  create: (body: CreateReservationRequest) => post<Reservation>('/reservations', body),
  /** Customer: own reservations · Waiter: reservations assigned to them. */
  list: (options?: Options) => get<Reservation[]>('/reservations', options),
  get: (reservationId: string, options?: Options) => get<Reservation>(`/reservations/${id(reservationId)}`, options),
  edit: (body: EditReservationRequest) => put<Reservation>('/reservations', body),
  cancel: (reservationId: string) => del<{ message: string }>('/reservations', { id: reservationId }),
  /** Waiter: 2 InProgress · 3 Completed · 1 Cancelled; terminal visits cannot be reopened. */
  updateStatus: (reservationId: string, newStatus: ReservationStatusCode) =>
    patch<{ message: string }>(`/reservations/${id(reservationId)}/status`, { newStatus }),
  /** Waiter: move the reservation to another table of their location. */
  changeTable: (reservationId: string, tableId: string) => patch<Reservation>(`/reservations/${id(reservationId)}/table`, { tableId }),
  feedbackToken: (reservationId: string) => get<{ token: string; expiresAt: string }>(`/reservations/${id(reservationId)}/feedback-token`),
  feedback: (reservationId: string, options?: Options) => get<ReservationFeedback>(`/reservations/${id(reservationId)}/feedback`, options),
  inviteToken: (reservationId: string) => get<{ token: string }>(`/reservations/${id(reservationId)}/invite-token`),
}

export const ordersApi = {
  /** Customer's orders (cancelled ones excluded). */
  list: (options?: Options) => get<Order[]>('/orders', options),
  /** 404 when the reservation has no active order — not shown as an error toast. */
  get: (reservationId: string, options?: Options) => get<Order>(`/orders/${id(reservationId)}`, options),
  create: (reservationId: string, orderItems: OrderLine[]) => post<Order>('/orders', { reservationId, orderItems }),
  edit: (reservationId: string, orderItems: OrderLine[]) => put<string>(`/orders/${id(reservationId)}`, { orderItems }),
  cancel: (reservationId: string) => del<string>(`/orders/${id(reservationId)}`),
  submit: (reservationId: string) => post<string>(`/orders/${id(reservationId)}/submit`),
  unsubmit: (reservationId: string) => post<string>(`/orders/${id(reservationId)}/unsubmit`),
  confirmDish: (reservationId: string, dishId: string) =>
    patch<{ message: string }>(`/reservations/${id(reservationId)}/order/confirmations/${id(dishId)}`),
  cancelDish: (reservationId: string, dishId: string) =>
    patch<{ message: string }>(`/reservations/${id(reservationId)}/order/cancellations/${id(dishId)}`),
}

export const feedbackApi = {
  forLocation: (locationId: string, type: 'Service' | 'CuisineExperience', sort: FeedbackSort, page: number, options?: Options) =>
    get<FeedbackPage>(`/feedback${query({ locationId, type, sort, page })}`, options),
  /** Anonymous (QR code) or signed-in customer; the backend recognises the customer from the idToken. */
  create: (body: FeedbackRequest) => post<Feedback>('/feedback', body),
  update: (body: FeedbackRequest) => put<{ message: string }>('/feedback', body),
}

export const notificationsApi = {
  unread: (options?: Options) => get<Notification[]>('/notifications', options),
  markRead: (notificationId: string) => patch<string>(`/notifications/${id(notificationId)}/read`),
}

export const reportsApi = {
  history: () => get<ReportHistoryItem[]>('/reports'),
  generate: (q: ReportQuery) => get<ReportRow[]>(`/reports/generate${query({ ...q })}`),
  download: (q: ReportQuery, format: ReportFormat): Promise<DownloadedFile> =>
    apiDownload(`/reports/download${query({ ...q, format })}`, `report_${q.startDate}-${q.endDate}.${format === 'excel' ? 'xlsx' : format}`),
}

/** Guest side of the group pre-order: authorised with the guest session token, not the user's idToken. */
export const guestApi = {
  /** Invite details; a guest who already joined passes their token so a full group still opens for them. */
  invite: (token: string, guestToken?: string, options?: Options) =>
    get<GuestInvite>(`/guest/invites/${id(token)}`, { ...options, guestToken }),
  createSession: (groupReservationId: string, guestName: string) =>
    post<GuestSessionCreated>('/guest/sessions', { groupReservationId, guestName }, { skipErrorToast: true }),
  session: (sessionId: string, guestToken: string) => get<GuestSessionInfo>(`/guest/sessions/${id(sessionId)}`, { guestToken }),
  menu: (sessionId: string, guestToken: string) => get<GuestMenu>(`/guest/sessions/${id(sessionId)}/menu`, { guestToken }),
  addDish: (sessionId: string, guestToken: string, dishId: string, quantity = 1) =>
    post<{ message: string }>(`/guest/sessions/${id(sessionId)}/dishes`, { dishId, quantity }, { guestToken }),
  removeDish: (sessionId: string, guestToken: string, dishId: string, quantity = 1) =>
    del<{ message: string }>(`/guest/sessions/${id(sessionId)}/dishes`, { dishId, quantity }, { guestToken }),
  submit: (sessionId: string, guestToken: string) => post<{ message: string }>(`/guest/sessions/${id(sessionId)}/submit`, undefined, { guestToken }),
}

export * from './types'
