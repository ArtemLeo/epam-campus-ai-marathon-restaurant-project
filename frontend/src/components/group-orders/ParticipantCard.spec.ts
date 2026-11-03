// Practice · participant card (port of homework-tests/practice/…/participant-card.component.spec.ts).
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ParticipantCard from './ParticipantCard.vue'
import type { Participant } from '@/models/group-orders/participant.model'

const OLENA: Participant = {
  id: 'olena',
  type: 'Guest',
  name: 'Olena',
  isSubmitted: false,
  total: 440,
  items: [{ dish: { id: 'dish2', name: 'Tom Yum', price: 220, imageUrl: '/assets/img/dishes/spring-salad.webp' }, quantity: 2 }],
}
const OWNER: Participant = { id: 'owner', type: 'Owner', name: 'Yevhenii', isSubmitted: true, total: 0, items: [] }

function render(participant: Participant): HTMLElement {
  return mount(ParticipantCard, { props: { participant } }).element as HTMLElement
}

describe('Practice · participant card', () => {
  describe('step 1 · card title', () => {
    it('guest: <h2> "Guest: Olena"', () => {
      expect(render(OLENA).querySelector('h2')?.textContent).toContain('Guest: Olena')
    })

    it('owner: <h2> "Owner: Yevhenii"', () => {
      expect(render(OWNER).querySelector('h2')?.textContent).toContain('Owner: Yevhenii')
    })
  })

  describe('step 3 · dishes and Subtotal', () => {
    it('shows the dish name, quantity and price × quantity as currency', () => {
      const text = render(OLENA).textContent ?? ''
      expect(text).toContain('Tom Yum')
      expect(text).toContain('2')
      expect(text).toContain('$440.00')
    })

    it("shows the participant's Subtotal", () => {
      expect(render(OLENA).textContent).toContain('Subtotal')
    })

    it('empty cart: "No dishes yet"', () => {
      expect(render(OWNER).textContent).toContain('No dishes yet')
    })

    it('the dish photo is 40×40', () => {
      const img = render(OLENA).querySelector('img')
      expect(img?.getAttribute('width')).toBe('40')
      expect(img?.getAttribute('height')).toBe('40')
    })
  })

  describe('step 4 · cart status as text', () => {
    it('"Still choosing" when the cart is not submitted', () => {
      expect(render(OLENA).textContent).toContain('Still choosing')
    })

    it('"Submitted" when it is submitted', () => {
      expect(render({ ...OLENA, isSubmitted: true }).textContent).toContain('Submitted')
    })
  })
})
