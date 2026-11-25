import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import LocationCard from './LocationCard.vue'

describe('LocationCard accessibility', () => {
  it('hides images that duplicate the visible location details', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/locations/:id', component: { template: '<div />' } }],
    })
    const wrapper = mount(LocationCard, {
      props: {
        location: {
          id: 'location-1',
          address: 'Main Street 1',
          description: 'City centre',
          totalCapacity: 20,
          averageOccupancy: '50%',
          imageUrl: '/restaurant.jpg',
          rating: 4.5,
        },
      },
      global: { plugins: [router] },
    })

    expect(wrapper.get('a').text()).toContain('Main Street 1')
    const decorativeImages = wrapper.findAll('img[aria-hidden="true"]')
    expect(decorativeImages).toHaveLength(2)
    expect(decorativeImages.every(image => image.attributes('alt') === '')).toBe(true)
    expect(wrapper.get('.location-card__rating img').attributes('alt')).toBe('Rating')
  })
})
