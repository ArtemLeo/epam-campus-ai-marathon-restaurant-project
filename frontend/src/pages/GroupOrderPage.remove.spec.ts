// Bonus · Remove Guest — page (port of homework-tests/level-3-bonus/pages/…/group-order-page.component.remove.spec.ts).
import { beforeEach, describe, expect, it, type Mocked } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import { ApiError } from '@/services/http/api-client'
import type { GroupOrdersService } from '@/services/group-orders/group-orders.service'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import { buttonByText, caesar, createServiceSpy, dialog, openStatus, renderPage } from '@/test/group-order-fixtures'

const SESSIONS: GroupSessionsResponse = {
  participants: [
    { id: 'owner', type: 'Owner', name: 'Yevhenii', isSubmitted: true, total: 180, items: [{ dish: caesar, quantity: 1 }] },
    { id: 'andrii', type: 'Guest', name: 'Andrii', isSubmitted: true, total: 360, items: [{ dish: caesar, quantity: 2 }] },
    { id: 'olena', type: 'Guest', name: 'Olena', isSubmitted: false, total: 180, items: [{ dish: caesar, quantity: 1 }] },
  ],
  total: 720,
}

function removeButtons(element: HTMLElement): HTMLButtonElement[] {
  return [...element.querySelectorAll('button')].filter((button) => button.textContent?.trim() === 'Remove Guest')
}

describe('Bonus · Remove Guest', () => {
  let service: Mocked<GroupOrdersService>

  beforeEach(() => {
    service = createServiceSpy(SESSIONS, openStatus(3))
  })

  it('"Remove Guest" is next to every guest and not next to the Owner', async () => {
    expect(removeButtons((await renderPage(service)).element)).toHaveLength(2)
  })

  it('the button has an aria-label with the name: "Remove Andrii"', async () => {
    expect(removeButtons((await renderPage(service)).element)[0]?.getAttribute('aria-label')).toBe('Remove Andrii')
  })

  it('click → dialog with the guest name → confirming removes and refreshes the list from the response', async () => {
    service.removeSession.mockResolvedValue({ participants: SESSIONS.participants.slice(0, 2), total: 540 })
    const { wrapper, element } = await renderPage(service)

    removeButtons(element)[1]?.click() // Olena
    await nextTick()
    const modal = dialog(element)
    expect(modal.textContent).toContain('Are you sure you want to remove')
    expect(modal.textContent).toContain('Olena')

    buttonByText(modal, 'Remove Guest')?.click()
    await flushPromises()

    expect(service.removeSession).toHaveBeenCalledOnce()
    expect(service.removeSession).toHaveBeenCalledWith('grp-1', 'olena')
    expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(2)
  })

  it('DELETE error: the list stays unchanged', async () => {
    service.removeSession.mockRejectedValue(new ApiError(400, 'Owner session cannot be removed.', null, ''))
    const { wrapper, element } = await renderPage(service)

    removeButtons(element)[1]?.click()
    await nextTick()
    buttonByText(dialog(element), 'Remove Guest')?.click()
    await flushPromises()

    expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(3)
  })

  it('no "Remove Guest" buttons after Submit', async () => {
    service.getStatus.mockResolvedValue({ currentParticipants: 3, maxCapacity: 5, status: 'Submitted' })
    expect(removeButtons((await renderPage(service)).element)).toHaveLength(0)
  })
})
