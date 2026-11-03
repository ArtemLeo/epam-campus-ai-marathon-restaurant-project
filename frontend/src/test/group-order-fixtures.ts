import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { vi, type Mocked } from 'vitest'
import GroupOrderPage from '@/pages/GroupOrderPage.vue'
import { GROUP_ORDERS_SERVICE, type GroupOrdersService } from '@/services/group-orders/group-orders.service'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import type { GroupStatusResponse } from '@/models/group-orders/group-status.model'
import type { GuestInvite } from '@/models/reservations/guest-invite.model'

/** Same fixtures as the Angular homework specs. */
export const caesar = { id: 'dish1', name: 'Caesar Salad', price: 180 }
export const tomYum = { id: 'dish2', name: 'Tom Yum', price: 220 }

export const INVITE = {
  GroupReservationId: 'grp-1',
  LocationAddress: 'Rustaveli Avenue 48',
  MaxGuestCount: 5,
  StartTime: '2026-10-21T16:00:00Z',
  EndTime: '2026-10-21T17:30:00Z',
} as GuestInvite

export const openStatus = (currentParticipants: number): GroupStatusResponse => ({
  currentParticipants,
  maxCapacity: 5,
  status: 'Open',
})

/** A spy service, like `jasmine.createSpyObj<GroupOrdersService>(…)` in the Angular specs. */
export function createServiceSpy(sessions: GroupSessionsResponse, status: GroupStatusResponse): Mocked<GroupOrdersService> {
  return {
    getGroupInvite: vi.fn<GroupOrdersService['getGroupInvite']>().mockResolvedValue(INVITE),
    getSessions: vi.fn<GroupOrdersService['getSessions']>().mockResolvedValue(structuredClone(sessions)),
    getOwnerSessionId: vi.fn<GroupOrdersService['getOwnerSessionId']>().mockResolvedValue('owner'),
    getStatus: vi.fn<GroupOrdersService['getStatus']>().mockResolvedValue(status),
    submit: vi.fn<GroupOrdersService['submit']>(),
    removeSession: vi.fn<GroupOrdersService['removeSession']>(),
  }
}

/** Mounts the page for `/reservations/res-1/group-order` and waits for the first load. */
export async function renderPage(service: GroupOrdersService) {
  const wrapper = mount(GroupOrderPage, {
    props: { reservationId: 'res-1' },
    global: {
      provide: { [GROUP_ORDERS_SERVICE]: service },
      stubs: { RouterLink: RouterLinkStub },
    },
  })
  await flushPromises()
  return { wrapper, element: wrapper.element as HTMLElement }
}

export function buttonByText(root: ParentNode, text: string): HTMLButtonElement | undefined {
  return [...root.querySelectorAll('button')].find((button) => button.textContent?.trim() === text)
}

export function dialog(element: HTMLElement): HTMLElement {
  const found = element.querySelector<HTMLElement>('[role="dialog"]')
  if (!found) throw new Error('expected an open <AppModal> dialog')
  return found
}
