import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { locale, t } from '@/i18n'
import type { Order } from '@/services/api'
import DraftOrderCard from './DraftOrderCard.vue'
import SentOrderCard from './SentOrderCard.vue'
import { buttonByText, caesar, createServiceSpy, openStatus, renderPage } from '@/test/group-order-fixtures'

const order: Order = {
  orderId: 'order-1', reservationId: 'reservation-1', reservationAddress: 'Rustaveli Avenue 48',
  reservationTime: 'Legacy English date', reservationStartTime: '2027-01-21T10:00:00Z',
  reservationEndTime: '2027-01-21T11:30:00Z', canEdit: true, editDisabledReason: null,
  groupSubmitted: false, status: 0,
  orderItems: [{ dish: { id: 'dish-custom', name: 'Soup', imageUrl: null, price: 10, translations: { uk: { name: 'Суп' }, de: { name: 'Suppe' } } } as Order['orderItems'][number]['dish'], quantity: 2, state: 0 }],
}

beforeEach(() => { locale.value = 'en' })
afterEach(() => { locale.value = 'en' })

describe('live order language changes', () => {
  it('updates cart labels, accessible actions, dates and status without changing order IDs', async () => {
    const draft = mount(DraftOrderCard, { props: { order } })
    const sent = mount(SentOrderCard, { props: { order: { ...order, status: 3 } } })
    try {
      expect(draft.text()).toContain('Submit Pre-order')
      expect(draft.text()).not.toContain('Legacy English date')
      expect(sent.text()).toContain('(Pending)')
      const englishTitle = draft.get('h4').text()

      locale.value = 'uk'
      await nextTick()
      expect(draft.text()).toContain('Надіслати замовлення')
      expect(draft.text()).toContain('Суп')
      expect(draft.find('[aria-label="Видалити страву «Суп»"]').exists()).toBe(true)
      expect(draft.get('h4').text()).toContain('Замовлення №order-1')
      expect(draft.get('h4').text()).not.toBe(englishTitle)
      expect(draft.find('[aria-label="Збільшити кількість"]').exists()).toBe(true)
      expect(sent.text()).toContain('(Очікує підтвердження)')
      expect(draft.text()).toContain('Rustaveli Avenue 48')
      await draft.get('[aria-label="Збільшити кількість"]').trigger('click')
      expect(draft.emitted('quantity')).toEqual([['dish-custom', 3]])

      locale.value = 'de'
      await nextTick()
      expect(draft.text()).toContain('Vorbestellung senden')
      expect(draft.text()).toContain('Suppe')
      expect(sent.text()).toContain('(Ausstehend)')
    } finally {
      draft.unmount()
      sent.unmount()
    }
  })

  it('updates the loaded group, Ukrainian plurals and the open confirmation without reloading data', async () => {
    const service = createServiceSpy({
      participants: [
        { id: 'owner', type: 'Owner', name: 'Olena', isSubmitted: true, total: 360, items: [{ dish: caesar, quantity: 2 }] },
        { id: 'guest', type: 'Guest', name: 'Andrii', isSubmitted: false, total: 0, items: [] },
      ], total: 360,
    }, openStatus(2))
    const { wrapper, element } = await renderPage(service)
    try {
      expect(wrapper.text()).toContain('Group Pre-Order')
      expect(wrapper.text()).toContain("1 participant hasn't submitted")
      buttonByText(element, 'Submit Pre-Order')?.click()
      await nextTick()
      expect(wrapper.get('[role="dialog"]').text()).toContain('Send 2 dishes')

      locale.value = 'uk'
      await nextTick()
      expect(wrapper.text()).toContain('Групове замовлення')
      expect(wrapper.text()).toContain('Моє замовлення')
      expect(wrapper.text()).toContain('Гість: Andrii')
      expect(wrapper.text()).toContain('1 учасник ще не надіслав')
      expect(wrapper.get('[role="dialog"]').text()).toContain('Надіслати до ресторану 2 страви')
      expect(t('orders.pendingParticipants', { count: 5 }, 5)).toContain('5 учасників')
      expect(t('orders.pendingParticipants', { count: 21 }, 21)).toContain('21 учасник')
      expect(service.getSessions).toHaveBeenCalledOnce()

      locale.value = 'fr'
      await nextTick()
      expect(wrapper.get('h1').text()).toBe('Précommande groupée')
      expect(wrapper.get('[role="dialog"]').text()).toContain('Envoyer 2 plats')
      expect(service.submit).not.toHaveBeenCalled()
    } finally { wrapper.unmount() }
  })
})
