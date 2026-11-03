// The dev-only mock backend answers only the demo reservation and lets everything else through.
import { beforeEach, describe, expect, it } from 'vitest'
import type { ApiRequest, MockHandler } from '@/services/http/api-client'
import { createDemoTokens } from '../auth/demo-auth'
import { createGroupOrdersMockHandler } from './group-orders.mock-handler'
import { DEMO_INVITE_TOKEN, GroupOrdersMockStore } from './group-orders.mock-store'

const request = (method: ApiRequest['method'], path: string, extra: Partial<ApiRequest> = {}): ApiRequest => ({
  method,
  path,
  url: `https://api.test${path}`,
  headers: {},
  body: undefined,
  ...extra,
})

describe('group orders mock handler (dev-only)', () => {
  let handle: MockHandler

  beforeEach(() => {
    handle = createGroupOrdersMockHandler(new GroupOrdersMockStore(), 0)
  })

  it('serves the demo reservation flow: invite token → invite → sessions', async () => {
    await expect(handle(request('GET', '/reservations/demo-reservation/invite-token'))).resolves.toEqual({
      status: 200,
      body: { token: DEMO_INVITE_TOKEN },
    })
    const invite = await handle(request('GET', `/guest/invites/${DEMO_INVITE_TOKEN}`))
    expect(invite?.body).toMatchObject({ GroupReservationId: 'demo-group', MaxGuestCount: 5 })
    const sessions = await handle(request('GET', '/guest/groups/demo-group/sessions'))
    expect(sessions?.body).toMatchObject({ total: 74.5 })
  })

  it('turns business errors into HTTP errors with an { error } body', async () => {
    await expect(handle(request('DELETE', '/guest/groups/demo-group/sessions/gs-owner'))).resolves.toEqual({
      status: 400,
      body: { error: 'Owner session cannot be removed.' },
    })
  })

  it('submits with the reservationId from the body', async () => {
    const response = await handle(request('POST', '/group-reservations/demo-group/submit', { body: { reservationId: 'demo-reservation' } }))
    expect(response?.status).toBe(200)
  })

  it('lets real reservations reach the API', () => {
    expect(handle(request('GET', '/reservations/real-id/invite-token'))).toBeUndefined()
    expect(handle(request('GET', '/guest/groups/real-group/sessions'))).toBeUndefined()
  })

  it('answers the header widgets with empty lists only for the demo token', async () => {
    const demo = { Authorization: `Bearer ${createDemoTokens().idToken}` }
    await expect(handle(request('GET', '/notifications', { headers: demo }))).resolves.toEqual({ status: 200, body: [] })
    expect(handle(request('GET', '/notifications', { headers: { Authorization: 'Bearer real.jwt.token' } }))).toBeUndefined()
  })
})
