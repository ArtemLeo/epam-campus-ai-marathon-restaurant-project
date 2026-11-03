// Level 2 · the page on API data. The service is a spy — the spec never touches the network
// (port of homework-tests/level-2/pages/group-order-page/group-order-page.component.spec.ts).
import { beforeEach, describe, expect, it, type Mocked } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import { useToast } from '@/composables/useToast'
import { ApiError } from '@/services/http/api-client'
import type { GroupOrdersService } from '@/services/group-orders/group-orders.service'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import type { SubmittedDish } from '@/models/group-orders/submit-group-pre-order.model'
import { buttonByText, caesar, createServiceSpy, dialog, openStatus, renderPage, tomYum } from '@/test/group-order-fixtures'

const SESSIONS: GroupSessionsResponse = {
  participants: [
    { id: 'owner', type: 'Owner', name: 'Yevhenii', isSubmitted: true, total: 180, items: [{ dish: caesar, quantity: 1 }] },
    { id: 'andrii', type: 'Guest', name: 'Andrii', isSubmitted: true, total: 360, items: [{ dish: caesar, quantity: 2 }] },
    { id: 'olena', type: 'Guest', name: 'Olena', isSubmitted: false, total: 220, items: [{ dish: tomYum, quantity: 1 }] },
  ],
  total: 760,
}

describe('Level 2 · Owner Review page', () => {
  let service: Mocked<GroupOrdersService>

  beforeEach(() => {
    service = createServiceSpy(SESSIONS, openStatus(3))
  })

  describe('data', () => {
    it('takes reservationId from the route and loads the group by GroupReservationId', async () => {
      await renderPage(service)
      expect(service.getGroupInvite).toHaveBeenCalledWith('res-1')
      expect(service.getSessions.mock.lastCall?.[0]).toBe('grp-1')
    })

    it('shows every participant; the own card is "My Pre-Order"', async () => {
      const { wrapper, element } = await renderPage(service)
      expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(3)
      expect(element.textContent).toContain('My Pre-Order')
      expect(element.textContent).toContain('Guest: Andrii')
    })

    it('status badge: "Collecting pre-orders"', async () => {
      expect((await renderPage(service)).element.textContent).toContain('Collecting pre-orders')
    })
  })

  describe('consolidated order — the main trap', () => {
    it('Grand Total counts only submitted carts: $540, not $760 from the API', async () => {
      const text = (await renderPage(service)).element.textContent ?? ''
      expect(text).toContain('$540.00')
      expect(text).not.toContain('$760.00')
    })

    it('the same dish is one line: "Caesar Salad × 3"', async () => {
      expect((await renderPage(service)).element.textContent).toContain('Caesar Salad × 3')
    })

    it('yellow banner: "1 participant hasn’t submitted…"', async () => {
      expect((await renderPage(service)).element.textContent).toMatch(/1 participant hasn.t submitted/)
    })
  })

  describe('screen states', () => {
    it('empty: "Participants haven’t added any dishes yet"', async () => {
      const empty = structuredClone(SESSIONS)
      empty.participants.forEach((person) => (person.items = []))
      service.getSessions.mockResolvedValue(empty)
      expect((await renderPage(service)).element.textContent).toMatch(/Participants haven.t added any dishes yet/)
    })

    it('404: "Group reservation not found"', async () => {
      service.getGroupInvite.mockRejectedValue(new ApiError(404, 'Reservation not found', null, ''))
      expect((await renderPage(service)).element.textContent).toContain('Group reservation not found')
    })

    it('any other error: "Try again" loads once more', async () => {
      service.getGroupInvite.mockRejectedValue(new ApiError(500, 'Server error', null, ''))
      const { element } = await renderPage(service)

      buttonByText(element, 'Try again')?.click()
      await flushPromises()

      expect(service.getGroupInvite).toHaveBeenCalledTimes(2)
    })
  })

  describe('Submit Pre-Order', () => {
    it('the button is disabled when nobody has submitted a cart', async () => {
      const nobody = structuredClone(SESSIONS)
      nobody.participants.forEach((person) => (person.isSubmitted = false))
      service.getSessions.mockResolvedValue(nobody)
      expect(buttonByText((await renderPage(service)).element, 'Submit Pre-Order')?.disabled).toBe(true)
    })

    it('"Submit Pre-Order" → dialog → "Submit": one request even on a double click', async () => {
      service.submit.mockReturnValue(new Promise<SubmittedDish[]>(() => {})) // never answers, like an open Subject
      const { element } = await renderPage(service)

      buttonByText(element, 'Submit Pre-Order')?.click()
      await nextTick()
      const modal = dialog(element)

      buttonByText(modal, 'Submit')?.click()
      await nextTick()
      buttonByText(modal, 'Submit')?.click()
      buttonByText(modal, 'Submitting…')?.click()
      await nextTick()

      expect(service.submit).toHaveBeenCalledOnce()
      expect(service.submit).toHaveBeenCalledWith('grp-1', 'res-1')
    })

    it('after success: "Sent to Restaurant", the Submit button is gone', async () => {
      service.submit.mockResolvedValue([{ dishId: 'dish1', quantity: 3 }])
      const { element } = await renderPage(service)

      buttonByText(element, 'Submit Pre-Order')?.click()
      await nextTick()
      buttonByText(dialog(element), 'Submit')?.click()
      await flushPromises()

      expect(element.textContent).toContain('Sent to Restaurant')
      expect(buttonByText(element, 'Submit Pre-Order')).toBeUndefined()
      expect(useToast().toasts.value.map((toast) => toast.message)).toContain('Pre-order sent to the restaurant')
    })

    it('submit error: the screen keeps working and the button can be pressed again', async () => {
      service.submit.mockRejectedValue(new ApiError(400, 'No submitted guest sessions', null, ''))
      const { element } = await renderPage(service)

      buttonByText(element, 'Submit Pre-Order')?.click()
      await nextTick()
      buttonByText(dialog(element), 'Submit')?.click()
      await flushPromises()

      expect(buttonByText(element, 'Submit Pre-Order')?.disabled).toBe(false)
    })
  })
})
