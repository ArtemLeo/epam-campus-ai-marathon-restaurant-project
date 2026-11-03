// Level 3 · keeping in sync with the backend: every 15 s while the group is Open
// (port of homework-tests/level-3/pages/group-order-page/group-order-page.component.sync.spec.ts).
// Fake timers stand in for fakeAsync + tick(15_000).
import { afterEach, beforeEach, describe, expect, it, vi, type Mocked } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import { ApiError } from '@/services/http/api-client'
import type { GroupOrdersService } from '@/services/group-orders/group-orders.service'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import { buttonByText, caesar, createServiceSpy, dialog, INVITE, openStatus, renderPage, tomYum } from '@/test/group-order-fixtures'

const SYNC_MS = 15_000
const SESSIONS: GroupSessionsResponse = {
  participants: [
    { id: 'owner', type: 'Owner', name: 'Yevhenii', isSubmitted: true, total: 180, items: [{ dish: caesar, quantity: 1 }] },
    { id: 'olena', type: 'Guest', name: 'Olena', isSubmitted: false, total: 220, items: [{ dish: tomYum, quantity: 1 }] },
  ],
  total: 400,
}

async function tick(ms: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms)
  await flushPromises()
}

describe('Level 3 · sync', () => {
  let service: Mocked<GroupOrdersService>

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'setTimeout', 'clearTimeout', 'Date'] })
    service = createServiceSpy(SESSIONS, openStatus(2))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('pulls fresh carts every 15 s — no page reload', async () => {
    const { element } = await renderPage(service)
    expect(element.textContent).toContain('Still choosing')

    const updated = structuredClone(SESSIONS)
    updated.participants[1]!.isSubmitted = true // Olena submitted her cart while the Owner was looking
    service.getSessions.mockResolvedValue(updated)
    await tick(SYNC_MS)

    expect(service.getSessions).toHaveBeenCalledTimes(2)
    expect(element.textContent).not.toContain('Still choosing')
  })

  it('background requests are silent: { silent: true }', async () => {
    await renderPage(service)
    await tick(SYNC_MS)
    expect(service.getSessions.mock.lastCall).toEqual(['grp-1', expect.objectContaining({ silent: true })])
    expect(service.getStatus.mock.lastCall).toEqual(['grp-1', expect.objectContaining({ silent: true })])
  })

  it('shows "Updated at …" and a "Refresh" button that syncs right away', async () => {
    const { element } = await renderPage(service)
    expect(element.textContent).toContain('Updated at')

    buttonByText(element, 'Refresh')?.click()
    await flushPromises()

    expect(service.getSessions).toHaveBeenCalledTimes(2)
  })

  it('background error: the data stays, "Couldn’t refresh"', async () => {
    const { wrapper, element } = await renderPage(service)
    service.getSessions.mockRejectedValue(new ApiError(500, 'Server error', null, ''))
    await tick(SYNC_MS)

    expect(element.textContent).toMatch(/Couldn.t refresh/)
    expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(2)
  })

  it('the sync stops after Submit', async () => {
    service.submit.mockResolvedValue([{ dishId: 'dish1', quantity: 1 }])
    const { element } = await renderPage(service)
    buttonByText(element, 'Submit Pre-Order')?.click()
    await nextTick()
    buttonByText(dialog(element), 'Submit')?.click()
    await flushPromises()

    await tick(SYNC_MS * 3)
    expect(service.getSessions).toHaveBeenCalledTimes(1)
  })

  it('the timer stops when the page is left', async () => {
    const { wrapper } = await renderPage(service)
    wrapper.unmount()
    await tick(SYNC_MS * 3)
    expect(service.getSessions).toHaveBeenCalledTimes(1)
  })

  // Extra checks for the level 3 conditions the Angular spec lists but does not test.

  it('"Try again" does not start a second timer', async () => {
    service.getGroupInvite.mockRejectedValueOnce(new ApiError(500, 'Server error', null, '')).mockResolvedValue(INVITE)
    const { element } = await renderPage(service)
    buttonByText(element, 'Try again')?.click()
    await flushPromises()

    await tick(SYNC_MS)
    expect(service.getSessions).toHaveBeenCalledTimes(2) // first load + exactly one sync
  })

  it('no new request while the previous one has not answered (exhaustMap)', async () => {
    await renderPage(service)
    service.getSessions.mockReturnValue(new Promise<GroupSessionsResponse>(() => {})) // a sync that hangs

    await tick(SYNC_MS * 3)
    expect(service.getSessions).toHaveBeenCalledTimes(2) // first load + the one hanging sync
  })
})
