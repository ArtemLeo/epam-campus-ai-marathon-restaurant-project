import { inject, type InjectionKey } from 'vue'
import { apiRequest } from '@/services/http/api-client'
import { reservationsApi, guestApi } from '@/services/api'
import type { GuestInvite } from '@/models/reservations/guest-invite.model'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import type { GroupStatusResponse } from '@/models/group-orders/group-status.model'
import type { OwnerSessionResponse } from '@/models/group-orders/owner-session.model'
import type { SubmitGroupPreOrderRequest, SubmittedDish } from '@/models/group-orders/submit-group-pre-order.model'

export interface RequestMode {
  /** Background sync: no error toast, the page shows "Couldn't refresh…" instead. */
  silent?: boolean
}

/** Owner side of the group pre-order (contract: homework-backend.md). */
export interface GroupOrdersService {
  getGroupInvite(reservationId: string): Promise<GuestInvite>
  getSessions(groupReservationId: string, mode?: RequestMode): Promise<GroupSessionsResponse>
  getOwnerSessionId(reservationId: string): Promise<string>
  getStatus(groupReservationId: string, mode?: RequestMode): Promise<GroupStatusResponse>
  submit(groupReservationId: string, reservationId: string): Promise<SubmittedDish[]>
  removeSession(groupReservationId: string, guestSessionId: string): Promise<GroupSessionsResponse>
}

const groupPath = (groupReservationId: string) => `/guest/groups/${encodeURIComponent(groupReservationId)}`

export const groupOrdersService: GroupOrdersService = {
  /** reservationId → invite token → invite (carries GroupReservationId and the header data). */
  async getGroupInvite(reservationId) {
    const { token } = await reservationsApi.inviteToken(reservationId)
    return guestApi.invite(token)
  },

  getSessions(groupReservationId, mode = {}) {
    return apiRequest<GroupSessionsResponse>(`${groupPath(groupReservationId)}/sessions`, {
      skipErrorToast: mode.silent === true,
    })
  },

  async getOwnerSessionId(reservationId) {
    const response = await apiRequest<OwnerSessionResponse>(
      `/reservations/${encodeURIComponent(reservationId)}/guest-session-id`,
    )
    return response.guestSessionId
  },

  getStatus(groupReservationId, mode = {}) {
    return apiRequest<GroupStatusResponse>(`${groupPath(groupReservationId)}/status`, {
      skipErrorToast: mode.silent === true,
    })
  },

  submit(groupReservationId, reservationId) {
    const body: SubmitGroupPreOrderRequest = { reservationId }
    return apiRequest<SubmittedDish[]>(`/group-reservations/${encodeURIComponent(groupReservationId)}/submit`, {
      method: 'POST',
      body,
    })
  },

  removeSession(groupReservationId, guestSessionId) {
    return apiRequest<GroupSessionsResponse>(
      `${groupPath(groupReservationId)}/sessions/${encodeURIComponent(guestSessionId)}`,
      { method: 'DELETE' },
    )
  },
}

/** Lets a test (or a story) swap the service, like Angular's `{ provide: GroupOrdersService, useValue }`. */
export const GROUP_ORDERS_SERVICE: InjectionKey<GroupOrdersService> = Symbol('GroupOrdersService')

export function useGroupOrdersService(): GroupOrdersService {
  return inject(GROUP_ORDERS_SERVICE, groupOrdersService)
}
