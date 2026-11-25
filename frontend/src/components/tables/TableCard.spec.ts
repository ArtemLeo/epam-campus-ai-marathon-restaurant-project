import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TableCard from './TableCard.vue'

describe('TableCard accessibility', () => {
  it('hides icons when adjacent text already describes the details', () => {
    const wrapper = mount(TableCard, {
      props: {
        table: {
          id: 'table-1',
          locationId: 'location-1',
          tableNumber: 7,
          capacity: 4,
          locationName: 'Main Hall',
        },
      },
    })

    expect(wrapper.text()).toContain('4 guests')
    expect(wrapper.text()).toContain('Main Hall')
    const icons = wrapper.findAll('img')
    expect(icons).toHaveLength(2)
    expect(icons.every(icon => icon.attributes('alt') === '')).toBe(true)
    expect(icons.every(icon => icon.attributes('aria-hidden') === 'true')).toBe(true)
  })
})
