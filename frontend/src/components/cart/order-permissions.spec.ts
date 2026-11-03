import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { Order } from '@/services/api'
import DraftOrderCard from './DraftOrderCard.vue'
import SentOrderCard from './SentOrderCard.vue'

const order: Order = {
  orderId: 'o1', reservationId: 'r1', reservationAddress: 'Restaurant', reservationTime: '1 Jan 2027, 14:00',
  reservationStartTime: '2027-01-01T10:00:00Z', reservationEndTime: '2027-01-01T11:30:00Z',
  canEdit: false, editDisabledReason: 'Submitted group orders are final.', groupSubmitted: true, status: 3,
  orderItems: [{ dish: { id: 'd1', name: 'Soup', imageUrl: null, price: 10 } as Order['orderItems'][number]['dish'], quantity: 1, state: 0 }],
}

describe('cart order permissions', () => {
  it('explains a final group order and does not offer invalid edit or cancel actions', () => {
    const wrapper = mount(SentOrderCard, { props: { order } })
    expect(wrapper.text()).toContain('Submitted group orders are final.')
    expect(wrapper.findAll('button')).toHaveLength(0)
  })
  it('disables every draft mutation after the editing deadline and shows the server reason', async () => {
    const wrapper = mount(DraftOrderCard, { props: { order: { ...order, status: 0, groupSubmitted: false, editDisabledReason: 'Pre-order changes close 30 minutes before your visit.' } } })
    expect(wrapper.text()).toContain('Pre-order changes close 30 minutes before your visit.')
    for (const button of wrapper.findAll('button')) {
      expect(button.element.disabled).toBe(true)
      await button.trigger('click')
    }
    expect(wrapper.emitted()).toEqual({})
  })
  it('keeps edit and cancel available for an eligible individual pre-order', async () => {
    const wrapper = mount(SentOrderCard, { props: { order: { ...order, canEdit: true, editDisabledReason: null, groupSubmitted: false } } })
    await wrapper.get('button.button--primary').trigger('click')
    expect(wrapper.emitted('edit')).toHaveLength(1)
  })
})
