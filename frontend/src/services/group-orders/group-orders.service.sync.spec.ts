// Level 3 · silent requests for the background sync: { silent: true } → no error toast
// (port of homework-tests/level-3/services/group-orders/group-orders.service.sync.spec.ts).
// Angular checks the SKIP_ERROR_TOAST HttpContext flag; here the equivalent flag is checked by its effect.
import { beforeEach, describe, expect, it } from 'vitest'
import { useToast } from '@/composables/useToast'
import { setApiBaseUrl } from '@/services/http/api-client'
import { fetchCall, mockFetch } from '@/test/fetch-mock'
import { groupOrdersService as service } from './group-orders.service'

const BASE_URL = 'https://api.test'
const SERVER_ERROR = { status: 500, body: { error: 'boom' } }

describe('Level 3 · silent service requests', () => {
  const { toasts } = useToast()

  beforeEach(() => setApiBaseUrl(BASE_URL))

  it('getSessions(id, { silent: true }) shows no toast on error', async () => {
    const fetchMock = mockFetch(SERVER_ERROR)

    await expect(service.getSessions('grp-1', { silent: true })).rejects.toMatchObject({ status: 500 })

    expect(fetchCall(fetchMock).url).toBe(`${BASE_URL}/guest/groups/grp-1/sessions`)
    expect(toasts.value).toHaveLength(0)
  })

  it('getStatus(id, { silent: true }) shows no toast on error', async () => {
    const fetchMock = mockFetch(SERVER_ERROR)

    await expect(service.getStatus('grp-1', { silent: true })).rejects.toMatchObject({ status: 500 })

    expect(fetchCall(fetchMock).url).toBe(`${BASE_URL}/guest/groups/grp-1/status`)
    expect(toasts.value).toHaveLength(0)
  })

  it('a normal request (no silent) shows the toast as usual', async () => {
    mockFetch(SERVER_ERROR)

    await expect(service.getSessions('grp-1')).rejects.toMatchObject({ status: 500 })

    expect(toasts.value).toHaveLength(1)
    expect(toasts.value[0]).toMatchObject({ type: 'error', title: 'Server Error' })
  })
})
