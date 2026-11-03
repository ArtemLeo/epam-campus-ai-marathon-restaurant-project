import type { Participant } from './participant.model'

/** GET /guest/groups/{groupReservationId}/sessions */
export interface GroupSessionsResponse {
  participants: Participant[]
  /** Sum of ALL participants, including the ones who have not submitted their cart yet. */
  total: number
}
