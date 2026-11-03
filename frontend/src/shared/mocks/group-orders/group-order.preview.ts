import type { GuestInvite } from '@/models/reservations/guest-invite.model'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import { DEMO_INVITE, DEMO_OWNER_SESSION_ID, GroupOrdersMockStore } from './group-orders.mock-store'

/**
 * Static data for LEVEL 1 (layout without HTTP).
 * The same data the mock backend serves, so the level 2 screen looks the same.
 */
export const GROUP_ORDER_PREVIEW: {
  invite: GuestInvite
  sessions: GroupSessionsResponse
  ownerSessionId: string
} = {
  invite: DEMO_INVITE,
  sessions: new GroupOrdersMockStore().snapshot(),
  ownerSessionId: DEMO_OWNER_SESSION_ID,
}
