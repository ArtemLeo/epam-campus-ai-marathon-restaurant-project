// The fetch-based client must behave like the Angular tokenInterceptor: bearer token, one error toast
// per failed request with the same wording, and an opt-out flag (SKIP_ERROR_TOAST).
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useToast } from '@/composables/useToast'
import { createDemoTokens } from '@/shared/mocks/auth/demo-auth'
import { apiRequest, ApiError, setApiBaseUrl, setMockHandler } from './api-client'
import { fetchCall, mockFetch } from '@/test/fetch-mock'

const { toasts } = useToast()

function lastToast() {
  return toasts.value.at(-1)
}

describe('apiRequest', () => {
  beforeEach(() => {
    setApiBaseUrl('https://api.test/')
    setMockHandler(undefined)
  })

  it('prefixes the base URL, sends JSON and returns the parsed body', async () => {
    const fetchMock = mockFetch({ body: { ok: true } })

    const result = await apiRequest<{ ok: boolean }>('/orders', { method: 'POST', body: { reservationId: 'r1' } })

    expect(result).toEqual({ ok: true })
    expect(fetchCall(fetchMock)).toMatchObject({
      url: 'https://api.test/orders',
      method: 'POST',
      body: { reservationId: 'r1' },
      headers: { 'Content-Type': 'application/json' },
    })
  })

  it("adds the user's idToken as a Bearer token", async () => {
    const tokens = createDemoTokens()
    localStorage.setItem('auth', JSON.stringify(tokens))
    const fetchMock = mockFetch({ body: [] })

    await apiRequest('/reservations')

    expect(fetchCall(fetchMock).headers.Authorization).toBe(`Bearer ${tokens.idToken}`)
  })

  it('does not send an expired idToken', async () => {
    localStorage.setItem('auth', JSON.stringify(createDemoTokens(Date.now() - 60 * 24 * 60 * 60 * 1000)))
    const fetchMock = mockFetch({ body: [] })

    await apiRequest('/reservations')

    expect(fetchCall(fetchMock).headers.Authorization).toBeUndefined()
  })

  it('uses the guest session token for the guest flow', async () => {
    localStorage.setItem('auth', JSON.stringify(createDemoTokens()))
    const fetchMock = mockFetch({ body: [] })

    await apiRequest('/guest/sessions/s1/menu', { guestToken: 'guest-token' })

    expect(fetchCall(fetchMock).headers.Authorization).toBe('Bearer guest-token')
  })

  it.each([
    { status: 400, body: { error: 'Table is busy' }, title: 'Error', message: 'Table is busy' },
    { status: 401, body: { error: 'nope' }, title: 'Unauthorized', message: 'Please log in to perform the action!' },
    { status: 403, body: { message: 'Only owner' }, title: 'Forbidden', message: 'Only owner' },
    { status: 404, body: null, title: 'Not Found', message: 'An unexpected error occurred.' },
    { status: 409, body: 'Already exists', title: 'Conflict', message: 'Already exists' },
    { status: 500, body: { error: 'Stack trace' }, title: 'Server Error', message: 'Server error. Please try again later.' },
  ])('shows one "$title" toast for $status and rejects with ApiError', async ({ status, body, title, message }) => {
    mockFetch({ status, body })

    const failure = apiRequest('/reservations')

    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status })
    expect(toasts.value).toHaveLength(1)
    expect(lastToast()).toMatchObject({ type: 'error', title, message })
  })

  it('words a 401 of the guest flow for guests', async () => {
    mockFetch({ status: 401 })

    await expect(apiRequest('/guest/sessions/s1', { guestToken: 'expired' })).rejects.toThrow()

    expect(lastToast()?.message).toBe('Session expired. Please re-open the invite link.')
  })

  it('skipErrorToast: rejects without a toast', async () => {
    mockFetch({ status: 500 })

    await expect(apiRequest('/reservations', { skipErrorToast: true })).rejects.toMatchObject({ status: 500 })

    expect(toasts.value).toHaveLength(0)
  })

  it('a missing pre-order (orders 404) is not reported as an error', async () => {
    mockFetch({ status: 404 })

    await expect(apiRequest('/orders/r1')).rejects.toMatchObject({ status: 404 })

    expect(toasts.value).toHaveLength(0)
  })

  it('a network failure becomes status 0 with a generic toast', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiRequest('/locations')).rejects.toMatchObject({ status: 0 })

    expect(lastToast()).toMatchObject({ title: 'Error', message: 'An unexpected error occurred.' })
  })

  it('lets a mock handler answer before the network', async () => {
    const fetchMock = mockFetch()
    setMockHandler((request) => (request.path === '/mocked' ? Promise.resolve({ status: 200, body: 'from mock' }) : undefined))

    await expect(apiRequest('/mocked?x=1')).resolves.toBe('from mock')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
