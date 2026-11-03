// Level 2 · GroupOrdersService: URL, method and body of every request
// (port of homework-tests/level-2/services/group-orders/group-orders.service.spec.ts).
import { beforeEach, describe, expect, it } from 'vitest'
import { setApiBaseUrl } from '@/services/http/api-client'
import { fetchCall, mockFetch } from '@/test/fetch-mock'
import { groupOrdersService as service } from './group-orders.service'

const BASE_URL = 'https://api.test'

describe('Level 2 · GroupOrdersService', () => {
  beforeEach(() => setApiBaseUrl(BASE_URL))

  it('getGroupInvite: reservationId → invite-token → invite', async () => {
    const fetchMock = mockFetch({ body: { token: 'tok' } }, { body: { GroupReservationId: 'grp-1' } })

    const invite = await service.getGroupInvite('res-1')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchCall(fetchMock, 0).url).toBe(`${BASE_URL}/reservations/res-1/invite-token`)
    expect(fetchCall(fetchMock, 1).url).toBe(`${BASE_URL}/guest/invites/tok`)
    expect(invite.GroupReservationId).toBe('grp-1')
  })

  it('getSessions: GET /guest/groups/{id}/sessions', async () => {
    const fetchMock = mockFetch({ body: { participants: [], total: 0 } })

    await service.getSessions('grp-1')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchCall(fetchMock)).toMatchObject({ url: `${BASE_URL}/guest/groups/grp-1/sessions`, method: 'GET' })
  })

  it('getOwnerSessionId: returns the guestSessionId string', async () => {
    const fetchMock = mockFetch({ body: { guestSessionId: 'owner-1' } })

    const id = await service.getOwnerSessionId('res-1')

    expect(fetchCall(fetchMock)).toMatchObject({ url: `${BASE_URL}/reservations/res-1/guest-session-id`, method: 'GET' })
    expect(id).toBe('owner-1')
  })

  it('getStatus: GET /guest/groups/{id}/status', async () => {
    const fetchMock = mockFetch({ body: { currentParticipants: 3, maxCapacity: 5, status: 'Open' } })

    await service.getStatus('grp-1')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchCall(fetchMock)).toMatchObject({ url: `${BASE_URL}/guest/groups/grp-1/status`, method: 'GET' })
  })

  it('submit: POST /group-reservations/{id}/submit with body { reservationId }', async () => {
    const fetchMock = mockFetch({ body: [] })

    await service.submit('grp-1', 'res-1')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchCall(fetchMock)).toMatchObject({
      url: `${BASE_URL}/group-reservations/grp-1/submit`,
      method: 'POST',
      body: { reservationId: 'res-1' },
    })
  })
})
