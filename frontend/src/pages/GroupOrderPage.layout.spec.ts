// Level 1 · page layout on the static preview data (port of homework-tests/level-1/…/group-order-page.component.spec.ts).
// Level 2 replaced the static import with the service, so the preview data now arrives through a stub service.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import type { GroupOrdersService } from '@/services/group-orders/group-orders.service'
import { GROUP_ORDER_PREVIEW } from '@/shared/mocks/group-orders/group-order.preview'
import { renderPage } from '@/test/group-order-fixtures'

describe('Level 1 · page layout', () => {
  let element: HTMLElement
  let host: HTMLElement
  let cards: number

  beforeEach(async () => {
    const service: GroupOrdersService = {
      getGroupInvite: vi.fn().mockResolvedValue(GROUP_ORDER_PREVIEW.invite),
      getSessions: vi.fn().mockResolvedValue(structuredClone(GROUP_ORDER_PREVIEW.sessions)),
      getOwnerSessionId: vi.fn().mockResolvedValue(GROUP_ORDER_PREVIEW.ownerSessionId),
      getStatus: vi.fn().mockResolvedValue({ currentParticipants: 4, maxCapacity: 5, status: 'Open' }),
      submit: vi.fn(),
      removeSession: vi.fn(),
    }
    const page = await renderPage(service)
    element = page.element
    host = element.parentElement as HTMLElement // like Angular's fixture.nativeElement host
    cards = page.wrapper.findAllComponents(ParticipantCard).length
  })

  it('one <main> and one <h1> "Group Pre-Order"', () => {
    expect(host.querySelectorAll('main').length).toBe(1)
    expect(host.querySelectorAll('h1').length).toBe(1)
    expect(host.querySelector('h1')?.textContent).toContain('Group Pre-Order')
  })

  it('header: address, date and "4 of 5 guests"', () => {
    const text = element.textContent ?? ''
    expect(text).toContain('Rustaveli Avenue 48')
    expect(text).toContain('Oct 21, 2026')
    expect(text).toContain('4 of 5 guests')
  })

  it('participants are a <ul>/<li> list of <article> cards', () => {
    expect(cards).toBe(4)
    expect(element.querySelectorAll('ul > li > article').length).toBe(4)
  })

  it('the cart status is visible as text', () => {
    expect(element.textContent).toContain('Submitted')
    expect(element.textContent).toContain('Still choosing')
  })

  it('Grand Total: $50.50 — only submitted carts (the level 2 rule replaces level 1’s $74.50 of all carts)', () => {
    const text = element.textContent ?? ''
    expect(text).toContain('Grand Total')
    expect(text).toContain('$50.50')
    expect(text).not.toContain('$74.50')
  })
})
