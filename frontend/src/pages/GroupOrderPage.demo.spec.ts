// The demo the homework is checked on (/reservations/demo-reservation/group-order?demo): real service,
// real API client and the dev-only mock backend — and not a single request to the network.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import { nextTick } from 'vue'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import { setMockHandler } from '@/services/http/api-client'
import { createGroupOrdersMockHandler } from '@/shared/mocks/group-orders/group-orders.mock-handler'
import { DEMO_RESERVATION_ID, GroupOrdersMockStore } from '@/shared/mocks/group-orders/group-orders.mock-store'
import { buttonByText, dialog } from '@/test/group-order-fixtures'
import GroupOrderPage from './GroupOrderPage.vue'

describe('Group Pre-Order on the dev mock backend', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    setMockHandler(createGroupOrdersMockHandler(new GroupOrdersMockStore(), 0))
  })

  afterEach(() => {
    setMockHandler(undefined)
  })

  async function renderDemo() {
    const wrapper = mount(GroupOrderPage, {
      props: { reservationId: DEMO_RESERVATION_ID },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    await vi.waitFor(() => expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(4))
    return { wrapper, element: wrapper.element as HTMLElement }
  }

  it('renders the demo group with the consolidated total of submitted carts', async () => {
    const { element } = await renderDemo()
    const text = element.textContent ?? ''

    expect(text).toContain('My Pre-Order')
    expect(text).toContain('4 of 5 guests')
    expect(text).toContain('Spring Salad × 3')
    expect(text).toContain('$50.50')
    expect(text).toMatch(/2 participants haven.t submitted/)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('removes a guest and then sends the pre-order to the restaurant', async () => {
    const { wrapper, element } = await renderDemo()

    element.querySelector<HTMLButtonElement>('[aria-label="Remove Mariana"]')?.click()
    await nextTick()
    buttonByText(dialog(element), 'Remove Guest')?.click()
    await vi.waitFor(() => expect(wrapper.findAllComponents(ParticipantCard)).toHaveLength(3))

    buttonByText(element, 'Submit Pre-Order')?.click()
    await nextTick()
    buttonByText(dialog(element), 'Submit')?.click()
    await vi.waitFor(() => expect(element.textContent).toContain('Sent to Restaurant'))
    await flushPromises()

    expect(element.querySelectorAll('[aria-label^="Remove "]')).toHaveLength(0)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
