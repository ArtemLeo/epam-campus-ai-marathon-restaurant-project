// Bonus · Remove Guest — service (port of homework-tests/level-3-bonus/services/…/group-orders.service.remove.spec.ts).
import { describe, expect, it } from 'vitest'
import { setApiBaseUrl } from '@/services/http/api-client'
import { fetchCall, mockFetch } from '@/test/fetch-mock'
import { groupOrdersService } from './group-orders.service'

describe('Bonus · removeSession', () => {
  it('DELETE /guest/groups/{id}/sessions/{guestSessionId}', async () => {
    setApiBaseUrl('https://api.test')
    const fetchMock = mockFetch({ body: { participants: [], total: 0 } })

    await groupOrdersService.removeSession('grp-1', 'gs-2')

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchCall(fetchMock)).toMatchObject({ url: 'https://api.test/guest/groups/grp-1/sessions/gs-2', method: 'DELETE' })
  })
})
