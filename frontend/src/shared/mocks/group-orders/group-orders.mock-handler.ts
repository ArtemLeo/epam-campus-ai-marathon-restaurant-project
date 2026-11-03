import type { ApiRequest, ApiResponse, MockHandler } from '@/services/http/api-client'
import { isDemoAuthorization } from '../auth/demo-auth'
import {
  DEMO_GROUP_ID,
  DEMO_INVITE,
  DEMO_INVITE_TOKEN,
  DEMO_OWNER_SESSION_ID,
  DEMO_RESERVATION_ID,
  GroupOrdersMockStore,
  MockHttpError,
} from './group-orders.mock-store'

const LATENCY_MS = 400

export const groupOrdersMockStore = new GroupOrdersMockStore()

/**
 * DEV-ONLY. Answers ONLY the requests of the demo reservation `demo-reservation` / `demo-group`;
 * everything else goes to the real API unchanged.
 * Open: /reservations/demo-reservation/group-order?demo  (?demo is the mock login, see ../auth/demo-auth.ts)
 */
export function createGroupOrdersMockHandler(
  store: GroupOrdersMockStore = groupOrdersMockStore,
  latencyMs = LATENCY_MS,
): MockHandler {
  const groupBase = `/guest/groups/${DEMO_GROUP_ID}/sessions`

  const respond = (handler: () => unknown): Promise<ApiResponse> =>
    new Promise((resolve) => setTimeout(resolve, latencyMs)).then(() => {
      try {
        return { status: 200, body: handler() }
      } catch (error) {
        if (error instanceof MockHttpError) return { status: error.status, body: { error: error.message } }
        throw error
      }
    })

  return ({ method, path, body, headers }: ApiRequest) => {
    if (method === 'GET' && path.endsWith(`/reservations/${DEMO_RESERVATION_ID}/invite-token`)) {
      return respond(() => ({ token: DEMO_INVITE_TOKEN }))
    }
    if (method === 'GET' && path.endsWith(`/guest/invites/${DEMO_INVITE_TOKEN}`)) {
      return respond(() => ({ ...DEMO_INVITE, MaxGuestCount: store.maxCapacity }))
    }
    if (method === 'GET' && path.endsWith(`/reservations/${DEMO_RESERVATION_ID}/guest-session-id`)) {
      return respond(() => ({ guestSessionId: DEMO_OWNER_SESSION_ID }))
    }
    if (method === 'GET' && path.endsWith(groupBase)) {
      return respond(() => store.snapshot())
    }
    if (method === 'GET' && path.endsWith(`/guest/groups/${DEMO_GROUP_ID}/status`)) {
      return respond(() => store.groupStatus())
    }
    if (method === 'POST' && path.endsWith(`/group-reservations/${DEMO_GROUP_ID}/submit`)) {
      return respond(() => store.submit((body as { reservationId?: string } | null)?.reservationId ?? ''))
    }
    if (method === 'DELETE' && path.includes(`${groupBase}/`)) {
      const guestSessionId = decodeURIComponent(path.slice(path.lastIndexOf('/') + 1))
      return respond(() => store.remove(guestSessionId))
    }

    // Demo login: the real API would reject the demo token, so the header widgets get empty lists.
    if (method === 'GET' && /\/(orders|notifications)$/.test(path) && isDemoAuthorization(headers.Authorization)) {
      return respond(() => [])
    }

    return undefined
  }
}
